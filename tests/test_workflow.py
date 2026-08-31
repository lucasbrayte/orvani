"""Offline contract tests for the scheduled affiliate synchronization."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest
import yaml


REPOSITORY_ROOT = Path(__file__).parents[1]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github/workflows/sync-affiliates.yml"
SELECTOR_PATH = REPOSITORY_ROOT / ".github/scripts/run-affiliate-sync.sh"
FULL_CRON = "17 3,15 * * *"
PENDING_CRON = "17 0-2,4-14,16-23 * * *"


def load_workflow() -> dict[str, object]:
    """Load workflow YAML through the active pytest interpreter's PyYAML."""
    workflow = yaml.load(WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(workflow, dict)
    return workflow


@pytest.mark.parametrize(
    ("mode", "expected_argv"),
    [
        ("pending", ["-m", "automation.cli", "sync", "--mode", "pending"]),
        ("full", ["-m", "automation.cli", "sync", "--mode", "full"]),
        ("validate", ["-m", "automation.cli", "validate"]),
    ],
)
def test_selector_invokes_cli_for_each_allowed_mode(tmp_path: Path, mode: str, expected_argv: list[str]):
    """Catches a selector branch that invokes the wrong CLI operation."""
    capture_path = tmp_path / "argv.txt"
    fake_python = tmp_path / "fake-python"
    fake_python.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$CAPTURE_PATH"\n', encoding="utf-8")
    fake_python.chmod(0o755)

    result = subprocess.run(
        [str(SELECTOR_PATH), mode],
        cwd=REPOSITORY_ROOT,
        env={**os.environ, "PYTHON_EXECUTABLE": str(fake_python), "CAPTURE_PATH": str(capture_path)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert capture_path.read_text(encoding="utf-8").splitlines() == expected_argv


@pytest.mark.parametrize("mode", ["", "unknown"])
def test_selector_rejects_modes_outside_the_allowlist(tmp_path: Path, mode: str):
    """Catches invalid input falling through to a write-capable sync mode."""
    capture_path = tmp_path / "argv.txt"
    fake_python = tmp_path / "fake-python"
    fake_python.write_text('#!/usr/bin/env bash\ntouch "$CAPTURE_PATH"\n', encoding="utf-8")
    fake_python.chmod(0o755)

    result = subprocess.run(
        [str(SELECTOR_PATH), mode],
        cwd=REPOSITORY_ROOT,
        env={**os.environ, "PYTHON_EXECUTABLE": str(fake_python), "CAPTURE_PATH": str(capture_path)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert not capture_path.exists()


def test_workflow_contract_limits_permissions_and_scopes_credentials():
    """Catches schedules or security scopes that can run unreviewed writes."""
    workflow = load_workflow()

    triggers = workflow["on"]
    assert isinstance(triggers, dict)
    dispatch = triggers["workflow_dispatch"]
    assert isinstance(dispatch, dict)
    mode_input = dispatch["inputs"]["mode"]
    assert mode_input == {
        "description": "Execution mode",
        "required": "true",
        "type": "choice",
        "options": ["pending", "full", "validate"],
    }
    schedules = triggers["schedule"]
    assert schedules == [{"cron": FULL_CRON}, {"cron": PENDING_CRON}]

    assert workflow["permissions"] == {"contents": "read"}
    concurrency = workflow["concurrency"]
    assert isinstance(concurrency, dict)
    assert concurrency["group"] == "affiliate-sync"
    assert concurrency["cancel-in-progress"] == "false"

    job = workflow["jobs"]["sync"]
    assert job["timeout-minutes"] == "20"
    assert "env" not in workflow
    assert "env" not in job

    steps = job["steps"]
    assert isinstance(steps, list)
    assert not any(step.get("uses", "").startswith("actions/upload-artifact") for step in steps)
    setup_python = next(step for step in steps if step.get("uses", "").startswith("actions/setup-python"))
    assert setup_python["with"] == {
        "python-version": "3.12",
        "cache": "pip",
        "cache-dependency-path": "requirements.txt\nrequirements-dev.txt\n",
    }

    cli_step = steps[-1]
    assert cli_step["run"] == ".github/scripts/run-affiliate-sync.sh \"$AFFILIATE_MODE\""
    assert cli_step["env"] == {
        "AFFILIATE_MODE": "${{ github.event_name == 'workflow_dispatch' && inputs.mode || (github.event.schedule == '17 3,15 * * *' && 'full' || 'pending') }}",
        "GOOGLE_SERVICE_ACCOUNT_JSON": "${{ secrets.GOOGLE_SERVICE_ACCOUNT_JSON }}",
        "ORVANI_IMPORT_WORKSHEET": "${{ vars.ORVANI_IMPORT_WORKSHEET }}",
        "ORVANI_PRODUCTS_WORKSHEET": "${{ vars.ORVANI_PRODUCTS_WORKSHEET }}",
    }
    assert all("GOOGLE_SERVICE_ACCOUNT_JSON" not in step.get("env", {}) for step in steps[:-1])
    assert all(
        not ({"ORVANI_IMPORT_WORKSHEET", "ORVANI_PRODUCTS_WORKSHEET"} & set(step.get("env", {})))
        for step in steps[:-1]
    )
