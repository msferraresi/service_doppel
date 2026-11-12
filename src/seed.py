from src.db.database import SessionLocal, init_db
from src.db.models import Endpoint, Scenario, Service


def seed_data():
    init_db()
    db = SessionLocal()

    # 1. Crear el servicio siniestro-reclamo si no existe
    svc = db.query(Service).filter(Service.name == "siniestro-reclamo").first()
    if not svc:
        svc = Service(
            name="siniestro-reclamo",
            description="Microservicio de gestión de reclamos y pagos de GDR",
            is_active=True,
        )
        db.add(svc)
        db.commit()
        db.refresh(svc)

    # 2. Crear el endpoint /gdr/{nu_ticket}/factura-honorarios
    path_pattern = "/gdr/{nu_ticket}/factura-honorarios"
    ep = (
        db.query(Endpoint)
        .filter(Endpoint.service_id == svc.id, Endpoint.path_pattern == path_pattern)
        .first()
    )

    if not ep:
        ep = Endpoint(
            service_id=svc.id,
            method="POST",
            path_pattern=path_pattern,
            mode="fixed",
        )
        db.add(ep)
        db.commit()
        db.refresh(ep)

    # 3. Escenario Éxito (200 OK)
    sc_success = (
        db.query(Scenario)
        .filter(Scenario.endpoint_id == ep.id, Scenario.name == "success_200")
        .first()
    )
    if not sc_success:
        sc_success = Scenario(
            endpoint_id=ep.id,
            name="success_200",
            status_code=200,
            delay_ms=80,
            weight=0.8,
            response_body={
                "nu_sec": 789012,
                "id_archivo": 345678,
                "numero_compromiso": 456789,
                "estado_ticket": 33,
                "descripcion_estado": "Pago de honorario en proceso",
                "factura_registrada": True,
                "pdf_digitalizado": True,
                "compromiso_generado": True,
            },
        )
        db.add(sc_success)
        db.commit()
        db.refresh(sc_success)

    # 4. Escenario Error (400 Bad Request)
    sc_error = (
        db.query(Scenario)
        .filter(
            Scenario.endpoint_id == ep.id, Scenario.name == "error_400_falta_reclamo"
        )
        .first()
    )
    if not sc_error:
        sc_error = Scenario(
            endpoint_id=ep.id,
            name="error_400_falta_reclamo",
            status_code=400,
            delay_ms=50,
            weight=0.2,
            response_body={
                "codigo": 400,
                "descripcion": "Falta nro. de reclamo",
                "detalle": None,
                "errorResponse": None,
                "detalles": None,
            },
        )
        db.add(sc_error)
        db.commit()

    # Fijamos el escenario de éxito como predeterminado
    ep.active_scenario_id = sc_success.id
    db.commit()
    db.close()
    print(
        "✅ Seed completado con éxito para ServiceDoppel (siniestro-reclamo configurado)."
    )


if __name__ == "__main__":
    seed_data()
