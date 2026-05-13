"""Health check endpoints: /healthz and /readyz."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from hermesfy.api.deps import get_settings
from hermesfy.api.settings import Settings
from hermesfy.storage.db import check_db_readiness

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    """Liveness probe — returns 200 if the process is running."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(settings: Settings = Depends(get_settings)) -> dict:
    """Readiness probe — checks DB, settings, and critical dependencies."""
    checks: dict[str, str] = {}

    # Check DB
    db_ok = await check_db_readiness(settings)
    checks["database"] = "ok" if db_ok else "error"

    # Check data dir writable
    from pathlib import Path
    data_dir = Path(settings.data_dir)
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        test_file = data_dir / ".readiness_test"
        test_file.write_text("ok")
        test_file.unlink()
        checks["data_dir"] = "ok"
    except Exception:
        checks["data_dir"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503

    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if all_ok else "degraded", "checks": checks},
    )
