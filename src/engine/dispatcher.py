import asyncio
import random
from typing import Optional

from fastapi import Request

from src.db.models import Endpoint, Scenario


def resolve_scenario(endpoint: Endpoint, request: Request) -> Optional[Scenario]:
    """Elige el escenario a retornar según el modo del endpoint o headers."""
    scenarios = endpoint.scenarios
    if not scenarios:
        return None

    # 1. Prioridad: Header forzado para tests específicos
    forced_scenario_name = request.headers.get("x-doppel-scenario")
    if forced_scenario_name:
        for sc in scenarios:
            if sc.name.lower() == forced_scenario_name.lower().strip():
                return sc

    # 2. Modo: Fixed (Escenario predeterminado configurado)
    if endpoint.mode == "fixed" and endpoint.active_scenario_id:
        for sc in scenarios:
            if sc.id == endpoint.active_scenario_id:
                return sc
        # Fallback al primero si no coincide el ID
        return scenarios[0]

    # 3. Modo: Random ponderado
    if endpoint.mode == "random":
        weights = [sc.weight or 1.0 for sc in scenarios]
        return random.choices(scenarios, weights=weights, k=1)[0]

    # Por defecto, devuelve el primer escenario cargado
    return scenarios[0]


async def simulate_delay(delay_ms: int):
    if delay_ms and delay_ms > 0:
        await asyncio.sleep(delay_ms / 1000.0)
