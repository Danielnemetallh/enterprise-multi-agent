"""Subprocess tests for CLI flows that never call DeepSeek."""

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(tmp_path, *args, env_overrides=None):
    env = {**os.environ, "SUPPORTFLOW_DB_PATH": str(tmp_path / "cli.db")}
    env.update(env_overrides or {})
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


def test_doctor_reports_demo_mode_without_live_call(tmp_path):
    result = json.loads(
        _run_cli(
            tmp_path,
            "doctor",
            "--live",
            env_overrides={"SUPPORTFLOW_DEMO_MODE": "true"},
        ).stdout
    )

    assert result["provider"] == "OpenAI-kompatibel"
    assert result["demo_mode"] is True
    assert result["live_check"] == "skipped_demo"


def test_demo_mode_runs_approval_flow_end_to_end(tmp_path):
    env = {"SUPPORTFLOW_DEMO_MODE": "true"}
    seeded = json.loads(_run_cli(tmp_path, "seed", "--force", env_overrides=env).stdout)
    assert seeded["imported"] == 5

    pending = json.loads(_run_cli(tmp_path, "process", "--ticket", "2", env_overrides=env).stdout)
    assert pending["status"] == "awaiting_review"

    completed = json.loads(
        _run_cli(
            tmp_path,
            "review",
            "--run",
            pending["run_id"],
            "--decision",
            "approve",
            "--reviewer",
            "interview-reviewer",
            env_overrides=env,
        ).stdout
    )

    assert completed["status"] == "completed"
    assert completed["approval_status"] == "approved"
    assert completed["case_file"]["policy_review"]["decision_source"] == "deterministic_policy"


def test_demo_mode_rejection_leaves_ticket_open(tmp_path):
    env = {"SUPPORTFLOW_DEMO_MODE": "true"}
    _run_cli(tmp_path, "seed", "--force", env_overrides=env)
    pending = json.loads(_run_cli(tmp_path, "process", "--ticket", "2", env_overrides=env).stdout)

    rejected = json.loads(
        _run_cli(
            tmp_path,
            "review",
            "--run",
            pending["run_id"],
            "--decision",
            "reject",
            "--reviewer",
            "interview-reviewer",
            env_overrides=env,
        ).stdout
    )
    queue = json.loads(_run_cli(tmp_path, "queue", env_overrides=env).stdout)

    assert rejected["status"] == "rejected"
    assert any(ticket["ticket_id"] == "DEMO-002" for ticket in queue)
