"""Simulated issuer FastAPI app.

Run:  python -m simulated_issuers.main
Env:  SIMULATED_ISSUERS_PORT=8001 (default). Busy port → clear exit error (no silent switch).
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path

# Allow `python -m simulated_issuers.main` from repo root
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fastapi import FastAPI

from simulated_issuers.config import get_settings
from simulated_issuers.middleware.latency import LatencyMiddleware
from simulated_issuers.middleware.outage import OutageMiddleware
from simulated_issuers.routers import (
    affidavit_estamp,
    aicte_payment,
    building_occupancy,
    fire_safety,
    icai_membership,
    structural_engineer,
)

app = FastAPI(
    title="PRAMAN Simulated Issuers",
    description="SIMULATED only — official_verification is always false. Not a real authority.",
    version="0.1.0",
)
app.add_middleware(OutageMiddleware)
app.add_middleware(LatencyMiddleware)

app.include_router(fire_safety.router)
app.include_router(building_occupancy.router)
app.include_router(structural_engineer.router)
app.include_router(aicte_payment.router)
app.include_router(icai_membership.router)
app.include_router(affidavit_estamp.router)


@app.get("/health")
def health():
    return {"status": "ok", "simulated": True}


def assert_port_available(host: str, port: int) -> None:
    # Do not set SO_REUSEADDR — on Windows it can mask an occupied listen port.
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # connect_ex == 0 means something is already accepting on host:port
        probe.settimeout(0.5)
        if probe.connect_ex((host, port)) == 0:
            raise SystemExit(
                f"ERROR: SIMULATED_ISSUERS_PORT={port} on {host} is already in use. "
                f"Free the port or set SIMULATED_ISSUERS_PORT to a free port. "
                f"Refusing to silently switch ports."
            )
    finally:
        probe.close()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError as exc:
            raise SystemExit(
                f"ERROR: SIMULATED_ISSUERS_PORT={port} on {host} is already in use. "
                f"Free the port or set SIMULATED_ISSUERS_PORT to a free port. "
                f"Refusing to silently switch ports. ({exc})"
            ) from exc


def main() -> None:
    import uvicorn

    settings = get_settings()
    assert_port_available(settings.host, settings.port)
    uvicorn.run(
        "simulated_issuers.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
