import uuid
from datetime import datetime

from ai_rfp_excel.app.api.runs import (
    CreateRunRequest,
    CreateSnapshotResponse,
    FingerprintGroup,
    QualityMetricsResponse,
    ReviewItem,
    RunDecisionResponse,
    RunInspectionItem,
    RunResponse,
    SubmitReviewRequest,
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
