"""Subprocess tests for CLI flows that never call DeepSeek."""

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(tmp_path, *args):
    env = {**os.environ, "SUPPORTFLOW_DB_PATH": str(tmp_path / "cli.db")}
    return subprocess.run(
        [sys.executable, "main.py", *args],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )


def test_seed_then_queue(tmp_path):
    seeded = json.loads(_run_cli(tmp_path, "seed", "--force").stdout)
    queued = json.loads(_run_cli(tmp_path, "queue").stdout)
    assert seeded["imported"] == 5
    assert [ticket["ticket_id"] for ticket in queued[:2]] == ["DEMO-003", "DEMO-002"]


def test_doctor_does_not_make_live_call(tmp_path):
    result = json.loads(_run_cli(tmp_path, "doctor").stdout)
    assert result["database_ready"] is True
    assert result["live_check"] == "not_requested"
