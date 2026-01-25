from __future__ import annotations

import os
import sys
import time
from pathlib import Path


TRUTHY = {"1", "true", "yes", "y", "on"}


def _die(message: str, code: int = 1) -> None:
    print(message)
    raise SystemExit(code)


def _env_value(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _runtime_env() -> str:
    return (
        _env_value("ENV")
        or _env_value("ENVIRONMENT")
        or _env_value("DEPLOY_ENV")
        or "dev"
    ).lower()


def _is_prod(env: str) -> bool:
    return env in {"prod", "production"}


def _parse_csv(value: str) -> list[str]:
    items: list[str] = []
    for part in (value or "").split(","):
        item = part.strip().upper()
        if item:
            items.append(item)
    return items


def _check_intent(env: str) -> None:
    if not _is_prod(env):
        return
    allow = _env_value("ALLOW_PROD_DEPLOY").lower() in TRUTHY
    if not allow:
        _die(
            "Refusing to deploy: ENV=prod without ALLOW_PROD_DEPLOY=1. "
            "Set ALLOW_PROD_DEPLOY=1 to confirm."
        )


def _check_alembic() -> None:
    alembic_ini = Path("alembic.ini")
    versions_dir = Path("alembic") / "versions"
    if not alembic_ini.exists():
        _die("Missing alembic.ini. Cannot verify migrations.")
    if not versions_dir.exists():
        _die("Missing alembic/versions. Cannot verify migrations.")
    if not list(versions_dir.glob("*.py")):
        _die("No migration files found in alembic/versions.")

    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
    except Exception as exc:
        _die(f"Alembic not available: {exc}")

    cfg = Config(str(alembic_ini))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    if not heads:
        _die("Alembic has no heads; migrations are missing or invalid.")
    for head in heads:
        if script.get_revision(head) is None:
            _die(f"Alembic head not reachable: {head}")


def _latest_backup_mtime(backup_dir: Path) -> float | None:
    if not backup_dir.exists():
        return None
    candidates = list(backup_dir.glob("nepxy_backup_*.dump"))
    if not candidates:
        return None
    return max(p.stat().st_mtime for p in candidates)


def _check_backup_recent(env: str) -> None:
    if not _is_prod(env):
        return
    backup_dir = Path(_env_value("BACKUP_DIR", "backups"))
    max_age_hours = int(_env_value("BACKUP_MAX_AGE_HOURS", "24"))
    latest = _latest_backup_mtime(backup_dir)
    if latest is None:
        _die(
            f"No backups found in {backup_dir}. "
            "Take a backup (scripts/db_backup.ps1 or scripts/db_backup.sh) before prod deploy."
        )
    age_hours = (time.time() - latest) / 3600.0
    if age_hours > max_age_hours:
        _die(
            f"Latest backup is too old ({age_hours:.1f}h). "
            f"Take a new backup (max age {max_age_hours}h)."
        )


def _check_required_env(env: str) -> None:
    missing: list[str] = []
    required = ["DATABASE_URL", "JWT_SECRET"]
    for name in required:
        if not _env_value(name):
            missing.append(name)
    if _env_value("JWT_SECRET") == "dev-secret-change-me":
        missing.append("JWT_SECRET")

    providers = _parse_csv(_env_value("MM_ENABLED_PROVIDERS", "TMONEY,FLOOZ,MTN_MOMO,THUNES"))
    if "TMONEY" in providers and not _env_value("TMONEY_WEBHOOK_SECRET"):
        missing.append("TMONEY_WEBHOOK_SECRET")
    if "FLOOZ" in providers and not _env_value("FLOOZ_WEBHOOK_SECRET"):
        missing.append("FLOOZ_WEBHOOK_SECRET")
    if "MTN_MOMO" in providers and not _env_value("MOMO_WEBHOOK_SECRET"):
        missing.append("MOMO_WEBHOOK_SECRET")
    if "THUNES" in providers and not _env_value("THUNES_WEBHOOK_SECRET"):
        missing.append("THUNES_WEBHOOK_SECRET")

    if missing:
        missing = sorted(set(missing))
        _die("Missing required env vars: " + ", ".join(missing))


def main() -> None:
    env = _runtime_env()
    print(f"Predeploy checks: env={env}")

    _check_intent(env)
    _check_alembic()
    _check_backup_recent(env)
    _check_required_env(env)

    print("Predeploy checks passed.")


if __name__ == "__main__":
    main()
