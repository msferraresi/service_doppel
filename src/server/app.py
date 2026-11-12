from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.db.database import SessionLocal, init_db
from src.db.models import Endpoint, RequestLog, Scenario, Service
from src.engine.dispatcher import resolve_scenario, simulate_delay
from src.engine.matcher import match_request_endpoint

app = FastAPI(title="ServiceDoppel - Mock Hub")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Endpoint de Catch-All para Simular los Servicios ---
@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def catch_all_router(
    request: Request, full_path: str, db: Session = Depends(get_db)
):
    # Ignorar llamadas a la documentación de Swagger de FastAPI
    if full_path in ["docs", "openapi.json", "redoc"]:
        raise HTTPException(status_code=404)

    method = request.method
    content_type = request.headers.get("content-type", "")

    form_fields = {}
    files_info = {}
    raw_body = None

    # Extracción de Multipart / Form-Data (PDFs o datos)
    if "multipart/form-data" in content_type:
        form = await request.form()
        for k, v in form.items():
            if hasattr(v, "filename"):  # UploadFile (ej: factura.pdf)
                content = await v.read()
                files_info[k] = {
                    "filename": v.filename,
                    "content_type": v.content_type,
                    "size_bytes": len(content),
                }
            else:
                form_fields[k] = str(v)
    else:
        try:
            body_bytes = await request.body()
            if body_bytes:
                raw_body = body_bytes.decode("utf-8", errors="replace")
        except Exception:
            pass

    # Match de endpoint en BD
    endpoint, path_params = match_request_endpoint(db, method, full_path)
    if not endpoint:
        return JSONResponse(
            status_code=404,
            content={
                "error": f"ServiceDoppel: No hay endpoint simulado configurado para [{method}] /{full_path}"
            },
        )

    # Resolución del escenario
    scenario = resolve_scenario(endpoint, request)
    if not scenario:
        return JSONResponse(
            status_code=500,
            content={
                "error": f"ServiceDoppel: El endpoint {endpoint.path_pattern} no tiene escenarios cargados."
            },
        )

    # Auditoría: Guardar el log de la llamada
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
    )
    db.add(audit)
    db.commit()

    # Simular latencia de red si está configurada
    await simulate_delay(scenario.delay_ms)

    # Retornar el body guardado en SQLite
    return JSONResponse(
        status_code=scenario.status_code, content=scenario.response_body
    )
