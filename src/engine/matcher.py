import json
import re
from typing import Any

from sqlalchemy.orm import Session

from src.db.models import Endpoint, Service


def pattern_to_regex(pattern: str) -> re.Pattern:
    cleaned = pattern.strip().strip("/")
    regex_str = re.sub(r"\{([a-zA-Z0-9_\-]+)\}", r"(?P<\1>[^/]+)", cleaned)
    return re.compile(f"^/?{regex_str}/?$")


def match_request_endpoint(
    db: Session, method: str, requested_path: str
) -> tuple[Endpoint | None, dict[str, Any]]:
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
            return ep, match.groupdict()

    return None, {}


def validate_incoming_payload(
    endpoint: Endpoint,
    raw_body: str | None,
    form_fields: dict,
    files_info: dict,
    query_params: dict,
) -> tuple[bool, str]:
    """Valida que el request entrante cumpla con expected_input configurado en BD."""
    contract = endpoint.expected_input or {}
    if not contract:
        return True, ""

    # Unificamos todos los datos recibidos (JSON body, form fields o query params)
    received_data = {}
    received_data.update(query_params)
    received_data.update(form_fields)

    if raw_body:
        try:
            parsed_json = json.loads(raw_body)
            if isinstance(parsed_json, dict):
                received_data.update(parsed_json)
        except json.JSONDecodeError:
            if contract.get("required_fields"):
                return (
                    False,
                    "Se esperaba un body JSON válido y llegó texto malformado.",
                )

    # 1. Validar campos obligatorios
    required_fields = contract.get("required_fields", [])
    missing = [
        f
        for f in required_fields
        if f not in received_data or received_data[f] in (None, "")
    ]
    if missing:
        return False, f"Faltan parámetros de entrada obligatorios: {', '.join(missing)}"

    # 2. Validar si exige archivo adjunto (ej. PDF en multipart)
    if contract.get("require_file") and not files_info:
        return (
            False,
            "El endpoint requiere al menos un archivo adjunto (multipart/form-data).",
        )

    return True, ""
