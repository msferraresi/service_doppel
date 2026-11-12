import asyncio
import copy
import random
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import Request

from src.db.models import Endpoint, Scenario


def resolve_scenario(endpoint: Endpoint, request: Request) -> Scenario | None:
    scenarios = endpoint.scenarios
    if not scenarios:
        return None

    # 1. Override explícito por header
    forced_name = request.headers.get("x-doppel-scenario")
    if forced_name:
        for sc in scenarios:
            if sc.name.lower() == forced_name.lower().strip():
                return sc

    # 2. Modo: SOLO ERRORES (status_code >= 400)
    if endpoint.mode == "errors_only":
        error_scenarios = [sc for sc in scenarios if sc.status_code >= 400]
        if error_scenarios:
            return random.choice(error_scenarios)
        return scenarios[0]

    # 3. Modo: ALEATORIO TOTAL
    if endpoint.mode == "random":
        weights = [sc.weight or 1.0 for sc in scenarios]
        return random.choices(scenarios, weights=weights, k=1)[0]

    # 4. Modo: FIJO
    if endpoint.active_scenario_id:
        for sc in scenarios:
            if sc.id == endpoint.active_scenario_id:
                return sc

    return scenarios[0]


def _resolve_value(
    key: str, template_val: Any, incoming_data: dict[str, Any], status_code: int
) -> Any:
    if isinstance(template_val, dict):
        return {
            k: _resolve_value(k, v, incoming_data, status_code)
            for k, v in template_val.items()
        }
    if isinstance(template_val, list):
        return [
            _resolve_value(key, item, incoming_data, status_code)
            for item in template_val
        ]

    if isinstance(template_val, str):
        token = template_val.strip().lower()
        placeholders = {
            "number",
            "int",
            "float",
            "decimal",
            "string",
            "boolean",
            "bool",
            "uuid",
            "date",
            "datetime",
            "echo",
            "auto",
        }

        if token in placeholders:
            # 1. Prioridad: si la clave vino en el request, devolver ese mismo valor (echo)
            if key in incoming_data and incoming_data[key] is not None:
                val = incoming_data[key]
                if token in {"number", "int"}:
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        return val
                if token in {"float", "decimal"}:
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        return val
                return val

            # 2. Si NO vino en el request, generar valor sintético según el tipo
            is_ok = status_code < 400
            if token in {"number", "int"}:
                return random.randint(100000, 999999)
            if token in {"float", "decimal"}:
                return round(random.uniform(10.0, 9999.99), 2)
            if token == "string":
                return "success" if is_ok else "error"
            if token in {"boolean", "bool"}:
                return is_ok
            if token == "uuid":
                return str(uuid.uuid4())
            if token == "date":
                return datetime.now(UTC).strftime("%Y-%m-%d")
            if token == "datetime":
                return datetime.now(UTC).isoformat()

    return copy.deepcopy(template_val)


def render_response_body(
    response_template: Any,
    incoming_data: dict[str, Any],
    status_code: int,
) -> Any:
    if isinstance(response_template, dict):
        return {
            k: _resolve_value(k, v, incoming_data, status_code)
            for k, v in response_template.items()
        }
    if isinstance(response_template, list):
        return [
            _resolve_value("", item, incoming_data, status_code)
            for item in response_template
        ]
    return response_template


async def simulate_delay(delay_ms: int):
    if delay_ms and delay_ms > 0:
        await asyncio.sleep(delay_ms / 1000.0)
