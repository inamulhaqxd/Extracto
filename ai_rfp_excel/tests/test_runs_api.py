import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from ai_rfp_excel.app.api.runs import (
    CreateRunRequest,
    CreateSnapshotResponse,
    DeleteAllRunsResponse,
    DeleteRunResponse,
    FingerprintGroup,
    QualityMetricsResponse,
    ReviewItem,
    RunDecisionResponse,
    RunInspectionItem,
    RunResponse,
    SubmitReviewRequest,
    delete_all_processing_runs,
    delete_processing_run,
)


def test_runs_models_validation() -> None:
    req = CreateRunRequest(
        pdf_document_id=str(uuid.uuid4()),
        workbook_id=str(uuid.uuid4()),
        model_name="qwen3:4b",
        vendor_name="Dell PowerStore",
    )
    assert req.model_name == "qwen3:4b"
    assert req.vendor_name == "Dell PowerStore"

    decision = RunDecisionResponse(
        requirement_id="REQ-001",
        requirement_text="128GB RAM",
        status="COMPLIANT",
        confidence=0.95,
        reasoning="Matches specs exactly.",
        resolving_layer="exact_match",
        evidence=[{"citation": "Page 3", "value": "128GB DDR5"}],
    )
    assert decision.requirement_id == "REQ-001"
    assert decision.confidence == 0.95
    assert decision.needs_review is False

    # Ambiguous item needs review
    amb_decision = RunDecisionResponse(
        requirement_id="REQ-002",
        requirement_text="256GB RAM",
        status="AMBIGUOUS",
        confidence=0.50,
        needs_review=True,
    )
    assert amb_decision.needs_review is True

    run_resp = RunResponse(
        run_id=str(uuid.uuid4()),
        status="completed",
        progress=100.0,
        current_step="Completed",
        total_requirements=2,
        compliant_count=1,
        ambiguous_count=1,
        decisions=[decision, amb_decision],
        started_at=datetime.now(),
    )
    assert run_resp.status == "completed"
    assert len(run_resp.decisions) == 2


def test_submit_review_request() -> None:
    review_req = SubmitReviewRequest(
        reviews=[
            ReviewItem(
                requirement_id="REQ-002",
                status="COMPLIANT",
                confidence=1.0,
                review_notes="Approved per customer addendum",
                slot_overrides={"answer": "400V 50Hz", "remarks": "Confirmed with vendor"},
            )
        ]
    )
    assert len(review_req.reviews) == 1
    assert review_req.reviews[0].status == "COMPLIANT"
    assert review_req.reviews[0].slot_overrides == {"answer": "400V 50Hz", "remarks": "Confirmed with vendor"}


def test_quality_metrics_models() -> None:
    fg = FingerprintGroup(
        fingerprint="spec:wb",
        label="Spec (Workbook)",
        sample_count=5,
        accuracy=0.80,
    )
    metrics = QualityMetricsResponse(
        total_runs=10,
        reviewed_runs=4,
        total_reviewed_examples=40,
        exact_correction_accuracy=0.875,
        low_confidence_failures=3,
        active_dataset_version="snapshot_20260906",
        layer_breakdown={"deterministic_rules": 10, "verified_llm": 25, "fallback": 5},
        fingerprint_groups=[fg],
    )
    assert metrics.total_runs == 10
    assert metrics.exact_correction_accuracy == 0.875
    assert len(metrics.fingerprint_groups) == 1

    item = RunInspectionItem(
        requirement_id="REQ-001",
        requirement_text="128GB RAM",
        predicted_status="COMPLIANT",
        predicted_value="128GB",
        confidence=0.95,
        reasoning="Matches",
        citation="Page 3",
        corrected_status="COMPLIANT",
        corrected_value="128GB",
        is_exact_match=True,
    )
    assert item.is_exact_match is True

    snap = CreateSnapshotResponse(
        snapshot_id="snapshot_20260906",
        file_path="/tmp/snapshot.jsonl",
        item_count=40,
        created_at="2026-09-06T12:00:00",
    )
    assert snap.item_count == 40


def test_delete_run_response_model() -> None:
    test_uuid = str(uuid.uuid4())
    res = DeleteRunResponse(
        message="Processing run and associated output files deleted successfully",
        run_id=test_uuid,
    )
    assert res.run_id == test_uuid
    assert "deleted successfully" in res.message


@pytest.mark.asyncio
async def test_delete_processing_run_endpoint(tmp_path: Path) -> None:
    run_uuid = uuid.uuid4()
    mock_run = MagicMock()
    mock_run.id = run_uuid

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_run
    mock_db.execute.return_value = mock_result

    gen_dir = tmp_path / str(run_uuid)
    gen_dir.mkdir(parents=True)
    dummy_file = gen_dir / "compliance_decisions.json"
    dummy_file.write_text("{}", encoding="utf-8")

    with patch("ai_rfp_excel.app.api.runs.settings.GENERATED_DIR", str(tmp_path)):
        mock_user = MagicMock()
        resp = await delete_processing_run(
            run_id=str(run_uuid),
            current_user=mock_user,
            db=mock_db,
        )

        assert resp.run_id == str(run_uuid)
        assert "deleted successfully" in resp.message
        assert not gen_dir.exists()
        mock_db.delete.assert_awaited_once_with(mock_run)
        mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_processing_run_not_found() -> None:
    run_uuid = uuid.uuid4()
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    mock_user = MagicMock()
    with pytest.raises(HTTPException) as exc_info:
        await delete_processing_run(
            run_id=str(run_uuid),
            current_user=mock_user,
            db=mock_db,
        )
    assert exc_info.value.status_code == 404


def test_delete_all_runs_response_model() -> None:
    res = DeleteAllRunsResponse(
        message="All processing runs and associated output files deleted successfully",
        deleted_count=5,
    )
    assert res.deleted_count == 5
    assert "deleted successfully" in res.message


@pytest.mark.asyncio
async def test_delete_all_processing_runs_endpoint(tmp_path: Path) -> None:
    run_uuid1 = uuid.uuid4()
    run_uuid2 = uuid.uuid4()
    mock_run1 = MagicMock()
    mock_run1.id = run_uuid1
    mock_run2 = MagicMock()
    mock_run2.id = run_uuid2

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_run1, mock_run2]
    mock_db.execute.return_value = mock_result

    # Create dummy directories
    gen_dir1 = tmp_path / str(run_uuid1)
    gen_dir1.mkdir(parents=True)
    gen_dir2 = tmp_path / str(run_uuid2)
    gen_dir2.mkdir(parents=True)

    with patch("ai_rfp_excel.app.api.runs.settings.GENERATED_DIR", str(tmp_path)):
        mock_user = MagicMock()
        resp = await delete_all_processing_runs(
            current_user=mock_user,
            db=mock_db,
        )

        assert resp.deleted_count == 2
        assert "All processing runs" in resp.message
        assert not gen_dir1.exists()
        assert not gen_dir2.exists()
        assert mock_db.delete.await_count == 2
        mock_db.commit.assert_awaited_once()


