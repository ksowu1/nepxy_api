from __future__ import annotations

from pathlib import Path


def test_promotion_drill_script_paths_exist():
    root = Path(__file__).resolve().parents[1]
    paths = [
        root / "scripts" / "promotion_drill.ps1",
        root / "scripts" / "_env_staging_from_fly.ps1",
        root / "scripts" / "canary_smoke.py",
        root / "scripts" / "db_backup_staging.ps1",
        root / "scripts" / "prod_smoke.ps1",
    ]
    missing = [p for p in paths if not p.exists()]
    assert not missing, f"Missing expected scripts: {missing}"
