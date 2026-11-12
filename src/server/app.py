import os
import sys
from datetime import datetime
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db.database import SessionLocal
from src.db.models import AppSetting, Endpoint, RequestLog, Scenario, Service
from src.engine.dispatcher import resolve_scenario, simulate_delay
from src.engine.matcher import match_request_endpoint, validate_incoming_payload

app = FastAPI(title="ServiceDoppel")


def get_index_html_path() -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        # Sube 2 niveles desde src/server/app.py hasta la raíz del proyecto
        base_path = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
    return os.path.join(base_path, "static", "index.html")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Schemas Admin ---
class ServiceCreate(BaseModel):
    name: str
    description: Optional[str] = None


class EndpointCreate(BaseModel):
    service_id: int
    method: str
    path_pattern: str
    required_fields: list[str] = []
    require_file: bool = False


class EndpointUpdate(BaseModel):
    method: str
    path_pattern: str
    required_fields: list[str] = []
    require_file: bool = False


class EndpointModeUpdate(BaseModel):
    mode: str
    active_scenario_id: Optional[int] = None


class ScenarioCreate(BaseModel):
    endpoint_id: int
    name: str
    status_code: int = 200
    delay_ms: int = 0
    weight: float = 1.0
    response_body: dict[str, Any]


class PortSettingUpdate(BaseModel):
    preferred_port: int


# --- Rutas Admin API ---
@app.get("/_admin/api/settings/port")
def get_port_settings(request: Request, db: Session = Depends(get_db)):
    setting = db.query(AppSetting).filter(AppSetting.key == "preferred_port").first()
    preferred = int(setting.value) if setting and setting.value.isdigit() else 8081
    active = getattr(request.app.state, "active_port", preferred)
    return {"preferred_port": preferred, "active_port": active}


@app.put("/_admin/api/settings/port")
def update_port_settings(data: PortSettingUpdate, db: Session = Depends(get_db)):
    if data.preferred_port < 1024 or data.preferred_port > 65535:
        raise HTTPException(400, "El puerto debe estar entre 1024 y 65535")
    setting = db.query(AppSetting).filter(AppSetting.key == "preferred_port").first()
    if setting:
        setting.value = str(data.preferred_port)
    else:
        db.add(AppSetting(key="preferred_port", value=str(data.preferred_port)))
    db.commit()
    return {"success": True}


@app.get("/_admin/api/services")
def list_services(db: Session = Depends(get_db)):
    services = db.query(Service).all()
    out = []
    for s in services:
        eps = []
        for ep in s.endpoints:
            scs = [
                {
                    "id": sc.id,
                    "name": sc.name,
                    "status_code": sc.status_code,
                    "delay_ms": sc.delay_ms,
                    "response_body": sc.response_body,
                }
                for sc in ep.scenarios
            ]
            eps.append(
                {
                    "id": ep.id,
                    "method": ep.method,
                    "path_pattern": ep.path_pattern,
                    "expected_input": ep.expected_input or {},
                    "mode": ep.mode,
                    "active_scenario_id": ep.active_scenario_id,
                    "scenarios": scs,
                }
            )
        out.append(
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "is_active": s.is_active,
                "endpoints": eps,
            }
        )
    return out


@app.post("/_admin/api/services")
def create_service(data: ServiceCreate, db: Session = Depends(get_db)):
    if db.query(Service).filter(Service.name == data.name.strip()).first():
        raise HTTPException(400, "El servicio ya existe")
    svc = Service(name=data.name.strip(), description=data.description)
    db.add(svc)
    db.commit()
    return {"success": True}


@app.delete("/_admin/api/services/{service_id}")
def delete_service(service_id: int, db: Session = Depends(get_db)):
    svc = db.query(Service).filter(Service.id == service_id).first()
    if svc:
        db.delete(svc)
        db.commit()
    return {"success": True}


@app.post("/_admin/api/endpoints")
def create_endpoint(data: EndpointCreate, db: Session = Depends(get_db)):
    path = data.path_pattern.strip()
    if not path.startswith("/"):
        path = "/" + path
    ep = Endpoint(
        service_id=data.service_id,
        method=data.method.upper(),
        path_pattern=path,
        expected_input={
            "required_fields": [f.strip() for f in data.required_fields if f.strip()],
            "require_file": data.require_file,
        },
        mode="fixed",
    )
    db.add(ep)
    db.commit()
    return {"success": True}


@app.put("/_admin/api/endpoints/{endpoint_id}")
def update_endpoint(
    endpoint_id: int, data: EndpointUpdate, db: Session = Depends(get_db)
):
    ep = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if not ep:
        raise HTTPException(404, "Endpoint no encontrado")
    path = data.path_pattern.strip()
    if not path.startswith("/"):
        path = "/" + path
    ep.method = data.method.upper()
    ep.path_pattern = path
    ep.expected_input = {
        "required_fields": [f.strip() for f in data.required_fields if f.strip()],
        "require_file": data.require_file,
    }
    db.commit()
    return {"success": True}


@app.delete("/_admin/api/endpoints/{endpoint_id}")
def delete_endpoint(endpoint_id: int, db: Session = Depends(get_db)):
    ep = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if ep:
        db.delete(ep)
        db.commit()
    return {"success": True}


@app.put("/_admin/api/endpoints/{endpoint_id}/behavior")
def update_endpoint_behavior(
    endpoint_id: int, data: EndpointModeUpdate, db: Session = Depends(get_db)
):
    ep = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if not ep:
        raise HTTPException(404, "Endpoint no encontrado")
    ep.mode = data.mode
    if data.active_scenario_id is not None:
        ep.active_scenario_id = data.active_scenario_id
    db.commit()
    return {"success": True}


@app.post("/_admin/api/scenarios")
def create_scenario(data: ScenarioCreate, db: Session = Depends(get_db)):
    ep = db.query(Endpoint).filter(Endpoint.id == data.endpoint_id).first()
    if not ep:
        raise HTTPException(404, "Endpoint no encontrado")
    sc = Scenario(
        endpoint_id=ep.id,
        name=data.name.strip(),
        status_code=data.status_code,
        delay_ms=data.delay_ms,
        weight=data.weight,
        response_body=data.response_body,
    )
    db.add(sc)
    db.commit()
    db.refresh(sc)
    if not ep.active_scenario_id:
        ep.active_scenario_id = sc.id
        db.commit()
    return {"success": True}


@app.delete("/_admin/api/scenarios/{scenario_id}")
def delete_scenario(scenario_id: int, db: Session = Depends(get_db)):
    sc = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if sc:
        db.delete(sc)
        db.commit()
    return {"success": True}


@app.get("/_admin/api/logs")
def list_logs(limit: int = 50, db: Session = Depends(get_db)):
    logs = db.query(RequestLog).order_by(RequestLog.id.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "received_at": l.received_at.strftime("%H:%M:%S") if l.received_at else "",
            "method": l.method,
            "path": l.path,
            "status": l.response_status,
            "raw_body": l.raw_body,
            "form_data": l.form_data,
            "files_info": l.files_info,
        }
        for l in logs
    ]


# --- Servir Panel Web desde static/index.html ---
@app.get("/_admin", include_in_schema=False)
@app.get("/_admin/", include_in_schema=False)
def serve_admin_panel():
    index_path = get_index_html_path()
    if not os.path.exists(index_path):
        return JSONResponse(
            status_code=500,
            content={"error": f"No se encontró el archivo HTML en: {index_path}"},
        )
    return FileResponse(index_path, media_type="text/html")


# --- Catch-All Router ---
@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def catch_all_router(
    request: Request, full_path: str, db: Session = Depends(get_db)
):
    if full_path.startswith("_admin") or full_path in ["docs", "openapi.json", "redoc"]:
        raise HTTPException(status_code=404)

    method = request.method
    content_type = request.headers.get("content-type", "")
    form_fields, files_info, raw_body = {}, {}, None

    if "multipart/form-data" in content_type:
        form = await request.form()
        for k, v in form.items():
            if hasattr(v, "filename"):
                content = await v.read()
                files_info[k] = {
                    "filename": v.filename,
                    "content_type": v.content_type,
                    "size_bytes": len(content),
                }
            else:
                form_fields[k] = str(v)
    else:
        body_bytes = await request.body()
        if body_bytes:
            raw_body = body_bytes.decode("utf-8", errors="replace")

    endpoint, _ = match_request_endpoint(db, method, full_path)
    if not endpoint:
        return JSONResponse(
            status_code=404,
            content={
                "error": f"ServiceDoppel: No existe mock para [{method}] /{full_path}"
            },
        )

    is_valid, error_msg = validate_incoming_payload(
        endpoint, raw_body, form_fields, files_info, dict(request.query_params)
    )
    if not is_valid:
        audit = RequestLog(
            endpoint_id=endpoint.id,
            received_at=datetime.utcnow(),
            method=method,
            path=f"/{full_path}",
            headers=dict(request.headers),
            query_params=dict(request.query_params),
            form_data=form_fields or None,
            files_info=files_info or None,
            raw_body=raw_body,
            response_status=400,
        )
        db.add(audit)
        db.commit()
        return JSONResponse(
            status_code=400,
            content={
                "codigo": 400,
                "descripcion": f"Validación ServiceDoppel: {error_msg}",
            },
        )

    scenario = resolve_scenario(endpoint, request)
    if not scenario:
        return JSONResponse(
            status_code=500,
            content={"error": "El endpoint no tiene escenarios configurados."},
        )

    audit = RequestLog(
        endpoint_id=endpoint.id,
        received_at=datetime.utcnow(),
        method=method,
        path=f"/{full_path}",
        headers=dict(request.headers),
        query_params=dict(request.query_params),
        form_data=form_fields or None,
        files_info=files_info or None,
        raw_body=raw_body,
        matched_scenario_id=scenario.id,
        response_status=scenario.status_code,
    )
    db.add(audit)
    db.commit()

    await simulate_delay(scenario.delay_ms)
    return JSONResponse(
        status_code=scenario.status_code, content=scenario.response_body
    )
