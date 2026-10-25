from __future__ import annotations

import pytest
from uuid import uuid4


@pytest.fixture()
def supervisor(monkeypatch):
    import gbt_allinone.tools.long_run_supervisor as module
    monkeypatch.setattr(module, "ROOT", module.STORE_DIR / f"long_runs_test_{uuid4().hex}")
    return module


def make_task(module, task_id="job-1", max_retries=2):
    return module.create(
        task_id,
        "持续产出并验证可归因收益的长视频",
        ["机会与收益假设", "长视频生产", "质量与收益复盘"],
        max_retries=max_retries,
        now="2026-09-21T00:00:00Z",
    )


def test_create_claim_heartbeat_and_complete_are_resumable(supervisor):
    task = make_task(supervisor)["task"]
    assert task["state"] == "planned"
    assert task["production_authorization"] == "required_at_release"

    claimed = supervisor.claim("job-1", "worker-a", now="2026-09-21T00:00:01Z")
    assert claimed["task"]["state"] == "running"
    beat = supervisor.heartbeat(
        "job-1", "worker-a", progress={"percent": 20}, checkpoint_ref="trace://cp-1",
        evidence=["sha256:abc"], now="2026-09-21T00:00:02Z")
    assert beat["task"]["state"] == "checkpointed"
    assert beat["task"]["checkpoint"]["ref"] == "trace://cp-1"

    result = supervisor.complete_step(
        "job-1", "worker-a", "step-001", evidence=["sha256:step-1"],
        now="2026-09-21T00:00:03Z")
    assert result["task"]["current_step"] == "step-002"
    again = supervisor.complete_step(
        "job-1", "worker-a", "step-001", evidence=["sha256:step-1"],
        now="2026-09-21T00:00:04Z")
    assert again["idempotent"] is True


def test_live_lease_cannot_be_stolen_and_expired_checkpoint_can_recover(supervisor):
    make_task(supervisor)
    supervisor.claim("job-1", "worker-a", now="2026-09-21T00:00:01Z")
    denied = supervisor.claim("job-1", "worker-b", now="2026-09-21T00:00:02Z")
    assert denied["denied"] is True
    supervisor.heartbeat(
        "job-1", "worker-a", checkpoint_ref="trace://cp", evidence=["sha256:cp"],
        now="2026-09-21T00:00:03Z")
    recovered = supervisor.recover("job-1", "worker-b", now="2026-09-21T00:04:00Z")
    assert recovered["task"]["worker_id"] == "worker-b"
    assert recovered["task"]["state"] == "running"


def test_expired_lease_without_checkpoint_escalates_instead_of_guessing(supervisor):
    make_task(supervisor)
    supervisor.claim("job-1", "worker-a", now="2026-09-21T00:00:01Z")
    decision = supervisor.tick("job-1", now="2026-09-21T00:04:00Z")
    assert decision["action"] == "escalate_owner"
    result = supervisor.recover("job-1", "worker-b", now="2026-09-21T00:04:00Z")
    assert result["denied"] is True
    assert result["task"]["state"] == "blocked"
    assert result["task"]["owner_action_required"] is True


def test_retry_backoff_is_bounded_and_exhaustion_blocks(supervisor):
    make_task(supervisor, max_retries=1)
    supervisor.claim("job-1", "worker-a", now="2026-09-21T00:00:01Z")
    first = supervisor.fail("job-1", "worker-a", "temporary", now="2026-09-21T00:00:02Z")
    assert first["retryable"] is True
    assert supervisor.tick("job-1", now="2026-09-21T00:00:10Z")["action"] == "wait_retry"
    assert supervisor.tick("job-1", now="2026-09-21T00:00:40Z")["action"] == "claim"
    supervisor.claim("job-1", "worker-b", now="2026-09-21T00:00:40Z")
    final = supervisor.fail("job-1", "worker-b", "still broken", now="2026-09-21T00:00:41Z")
    assert final["retryable"] is False
    assert final["task"]["state"] == "blocked"


def test_wrong_worker_and_missing_evidence_fail_closed(supervisor):
    make_task(supervisor)
    supervisor.claim("job-1", "worker-a", now="2026-09-21T00:00:01Z")
    with pytest.raises(PermissionError):
        supervisor.heartbeat("job-1", "worker-b", now="2026-09-21T00:00:02Z")
    with pytest.raises(ValueError):
        supervisor.complete_step("job-1", "worker-a", "step-001", evidence=[],
                                 now="2026-09-21T00:00:03Z")


def test_status_lists_persisted_tasks(supervisor):
    make_task(supervisor, "job-a")
    make_task(supervisor, "job-b")
    result = supervisor.status()
    assert [item["task_id"] for item in result["tasks"]] == ["job-a", "job-b"]


def test_revenue_video_blueprint_is_complete_and_keeps_hard_gates(supervisor):
    blueprint = supervisor.revenue_video_blueprint()
    assert len(blueprint["cycle"]) == 10
    assert blueprint["cycle"][0]["key"] == "opportunity"
    assert blueprint["cycle"][-1]["key"] == "publish_learn"
    assert "主人发布授权" in blueprint["gates"]
    assert "净收益" in blueprint["optimization_metrics"]


def test_mindmap_compiles_fixed_trigger_structure(supervisor):
    mindmap = supervisor.revenue_video_mindmap()
    ids = {node["id"] for node in mindmap["nodes"]}
    assert {"goal", "trigger", "plan", "produce", "audit", "release", "learn"} <= ids
    assert len(mindmap["nodes"]) == len(ids)
    assert "主人授权" in mindmap["compile_contract"]["release_policy"]
