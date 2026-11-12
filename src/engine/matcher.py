import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.db.models import Endpoint, Service


def pattern_to_regex(pattern: str) -> re.Pattern:
    """Convierte /gdr/{nu_ticket}/factura-honorarios en regex compatible."""
    cleaned = pattern.strip().strip("/")
    # Reemplaza {nombre_param} por grupo de captura con nombre
    regex_str = re.sub(r"\{([a-zA-Z0-9_\-]+)\}", r"(?P<\1>[^/]+)", cleaned)
    return re.compile(f"^/?{regex_str}/?$")


def match_request_endpoint(
    db: Session, method: str, requested_path: str
) -> tuple[Optional[Endpoint], dict[str, Any]]:
    """Busca en la base si la ruta y método coinciden con algún endpoint activo."""
    # Obtenemos los endpoints de servicios activos
    endpoints = (
        db.query(Endpoint)
        .join(Service)
        .filter(Service.is_active == True, Endpoint.method == method.upper())
        .all()
    )

    clean_requested = requested_path.strip().strip("/")

    for ep in endpoints:
        regex = pattern_to_regex(ep.path_pattern)
        match = regex.match(clean_requested)
        if match:
            # Devuelve el endpoint y el diccionario de path params (ej: {'nu_ticket': '12048'})
            return ep, match.groupdict()

    return None, {}
