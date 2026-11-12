import asyncio
import random
from typing import Optional
from fastapi import Request
from src.db.models import Endpoint, Scenario


def resolve_scenario(endpoint: Endpoint, request: Request) -> Optional[Scenario]:
    scenarios = endpoint.scenarios
    if not scenarios:
        return None

    # 1. Override explícito por header (opcional desde Postman/Java)
    forced_name = request.headers.get("x-doppel-scenario")
    if forced_name:
        for sc in scenarios:
            if sc.name.lower() == forced_name.lower().strip():
                return sc

    # 2. Modo: SOLO ERRORES (cualquier escenario con status_code >= 400)
    if endpoint.mode == "errors_only":
        error_scenarios = [sc for sc in scenarios if sc.status_code >= 400]
        if error_scenarios:
            return random.choice(error_scenarios)
        return scenarios[0]

    # 3. Modo: ALEATORIO TOTAL (entre 200, 400, 500, etc.)
    if endpoint.mode == "random":
        weights = [sc.weight or 1.0 for sc in scenarios]
        return random.choices(scenarios, weights=weights, k=1)[0]

    # 4. Modo: FIJO (el escenario activo seleccionado en la UI)
    if endpoint.active_scenario_id:
        for sc in scenarios:
            if sc.id == endpoint.active_scenario_id:
                return sc

    return scenarios[0]


async def simulate_delay(delay_ms: int):
    if delay_ms and delay_ms > 0:
        await asyncio.sleep(delay_ms / 1000.0)
