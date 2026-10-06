#!/usr/bin/env python3
"""Static contract tests for the Editor-in-Chief newsroom hierarchy.

These tests intentionally fail if a leaf robot regains its own schedule/push
trigger, dispatches another leaf robot directly, loses its callback to the
Editor-in-Chief, or if Pages mutates newsroom data instead of deploying the
exact repository state.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "newsroom-robots.json"
ASSIGNMENT_PATH = ROOT / ".github" / "workflows" / "editor-in-chief-newsroom-assignment.yml"
AUDITOR_PATH = ROOT / ".github" / "workflows" / "editor-in-chief-maintenance.yml"


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def on_block(text: str) -> str:
    match = re.search(r"(?ms)^on:\n(.*?)(?=^permissions:)", text)
    if not match:
        raise AssertionError("workflow has no parseable on:/permissions: block")
    return match.group(1)


registry = json.loads(read(REGISTRY_PATH))
assert registry.get("schemaVersion") == 2, registry.get("schemaVersion")
assert registry.get("principles", {}).get("singleNormalDispatcher") is True
assert registry.get("principles", {}).get("outcomeVerificationRequired") is True
assert registry.get("controlPlane", {}).get("leafRobotsManualDispatchOnly") is True

robots = registry.get("robots") or []
by_id = {str(r.get("id")): r for r in robots if isinstance(r, dict)}
assert int(by_id["collector"]["standingDuty"]["cadenceMinutes"]) == 15
assert int(by_id["collector"]["standingDuty"]["dueAfterMinutes"]) <= 15
assert int(by_id["stock"]["standingDuty"]["cadenceMinutes"]) == 60
assert isinstance(by_id["stock"]["standingDuty"]["activeHoursHKT"], list)
assert robots, "robot registry is empty"
workflow_to_robot = {}
for robot in robots:
    robot_id = str(robot.get("id") or "").strip()
    workflow = str(robot.get("workflow") or "").strip()
    assert robot_id and workflow, robot
    assert workflow not in workflow_to_robot, f"duplicate workflow in registry: {workflow}"
    workflow_to_robot[workflow] = robot_id

leaf_text = {}
for workflow, robot_id in workflow_to_robot.items():
    path = ROOT / ".github" / "workflows" / workflow
    text = read(path)
    leaf_text[workflow] = text
    block = on_block(text)

    assert "workflow_dispatch:" in block, f"{robot_id}: workflow_dispatch missing"
    assert re.search(r"(?m)^\s*schedule:", block) is None, f"{robot_id}: autonomous schedule forbidden"
    assert re.search(r"(?m)^\s*push:", block) is None, f"{robot_id}: autonomous push trigger forbidden"
    assert re.search(r"(?m)^\s*workflow_run:", block) is None, f"{robot_id}: leaf workflow_run trigger forbidden"
    assert re.search(r"(?ms)^permissions:\n.*?actions:\s*write", text), f"{robot_id}: callback requires actions: write"
    assert "editor-in-chief-newsroom-assignment.yml" in text, f"{robot_id}: outcome callback to Editor-in-Chief missing"
    assert "trigger_workflow=" in text, f"{robot_id}: callback workflow identity missing"
    assert "trigger_conclusion=" in text, f"{robot_id}: callback conclusion missing"
    assert "trigger_run_id=" in text, f"{robot_id}: callback run id missing"

# Leaf robots may not dispatch any other registered leaf robot.
registered_workflows = sorted(workflow_to_robot)
for source_workflow, text in leaf_text.items():
    source_robot = workflow_to_robot[source_workflow]
    for target_workflow in registered_workflows:
        if target_workflow == source_workflow:
            continue
        patterns = [
            rf"gh\s+workflow\s+run\s+['\"]?{re.escape(target_workflow)}",
            rf"/actions/workflows/{re.escape(target_workflow)}/dispatches",
        ]
        for pattern in patterns:
            assert re.search(pattern, text) is None, (
                f"{source_robot}: direct leaf-to-leaf dispatch to {target_workflow} is forbidden"
            )

# Pages is a deployment robot only. It must not mutate/rebuild newsroom content.
pages = leaf_text["pages.yml"]
for forbidden in (
    "python scripts/merge_live_into_desk.py",
    "python scripts/build_today_daily_from_desk.py",
    "python scripts/generate_daily_vocab.py",
    "python scripts/stock_verified_producer.py",
):
    assert forbidden not in pages, f"Pages contains newsroom mutation: {forbidden}"

# Vocab is TODAY-FIRST only; historical gaps cannot block today's publication.
vocab = leaf_text["daily-japanese-vocab.yml"]
assert "TODAY_FIRST_VOCAB" in vocab
assert "historical_backfill=disabled" in vocab
assert "Backfilling daily vocab" not in vocab
assert "while [[ \"$NEXT\"" not in vocab

# The sole dispatcher must be writable, durable, and outcome-aware.
assignment = read(ASSIGNMENT_PATH)
assignment_on = on_block(assignment)
assert "workflow_run:" not in assignment_on, "normal callbacks must use explicit workflow_dispatch, not workflow_run chaining"
assert "schedule:" in assignment_on, "dispatcher safety-net schedule missing"
assert "workflow_dispatch:" in assignment_on, "dispatcher callback endpoint missing"
assert "trigger_workflow:" in assignment_on, "dispatcher callback workflow input missing"
assert "trigger_conclusion:" in assignment_on, "dispatcher callback conclusion input missing"
assert "trigger_run_id:" in assignment_on, "dispatcher callback run-id input missing"
assert re.search(r"(?ms)^permissions:\n.*?contents:\s*write", assignment), "assignment telemetry requires contents: write"
assert "cancel-in-progress: false" in assignment
assert "editor-assignments" in assignment
assert "--previous-assignments" in assignment
assert "--trigger-workflow" in assignment
assert "--trigger-run-id" in assignment
assert "dispatchInputs" in assignment
assert "maxRuntimeMinutes" in assignment

# The auditor may delegate only to the assignment control plane, never directly
# to leaf robots. The dispatcher owns normal robot execution.
auditor = read(AUDITOR_PATH)
assert "editor-in-chief-newsroom-assignment.yml" in auditor
for workflow in registered_workflows:
    assert re.search(
        rf"gh\s+workflow\s+run\s+['\"]?{re.escape(workflow)}",
        auditor,
    ) is None, f"auditor directly dispatches leaf robot {workflow}"

print(
    "NEWSROOM_ORCHESTRATION_CONTRACT_OK",
    f"robots={len(robots)}",
    "single_dispatcher=editor-in-chief-newsroom-assignment.yml",
)
