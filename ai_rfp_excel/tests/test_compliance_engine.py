import json
import pytest

from ai_rfp_excel.app.ai.mock_provider import MockLLMProvider
from ai_rfp_excel.app.matching.engine import ComplianceEngine
from ai_rfp_excel.app.matching.layers.exact import ExactMatchLayer
from ai_rfp_excel.app.matching.layers.rules import RuleBasedLayer
from ai_rfp_excel.app.matching.layers.semantic import SemanticMatchLayer
from ai_rfp_excel.app.matching.layers.unit_matching import UnitConversionLayer
from ai_rfp_excel.app.matching.layers.units import (
    compare_quantities,
    normalize_unit_string,
    parse_numeric_with_unit,
)
from ai_rfp_excel.app.matching.models import (
    ComplianceState,
    FactItem,
)


def test_unit_helpers_parsing_and_normalization() -> None:
    # Parsing
    p_gb = parse_numeric_with_unit("256GB")
    assert p_gb is not None
    assert p_gb[0] == 256.0
    assert p_gb[1] == "gb"
    assert p_gb[2] == 256.0 * (1024**3)

    p_tb = parse_numeric_with_unit("100 terabytes")
    assert p_tb is not None
    assert p_tb[0] == 100.0
    assert p_tb[1] == "terabytes"

    # Normalization
    assert normalize_unit_string("64 gigabytes") == "64GB"
    assert normalize_unit_string("100 Terabytes") == "100TB"
    assert normalize_unit_string("2.4 GHz") == "2.4GHz"
    assert normalize_unit_string("10 Gbps") == "10Gbps"

    # Comparisons
    assert compare_quantities("100TB", "50TB", ">=") is True
    assert compare_quantities("50TB", "100TB", ">=") is False
    assert compare_quantities("1024GB", "1TB", "=") is True
    assert compare_quantities("2.4GHz", "2400MHz", "=") is True


def test_layer1_exact_match() -> None:
    layer = ExactMatchLayer()
    facts = [
        FactItem(
            field_name="CPU Model",
            value="Intel Xeon Gold 6430",
            source_page=4,
            source_table_id="T4-1",
        )
    ]

    res = layer.evaluate("Intel Xeon Gold 6430", facts)
    assert res is not None
    assert res.state == ComplianceState.COMPLIANT
    assert res.confidence == 1.0
    assert res.layer_name == "exact_match"
    assert len(res.evidence) == 1
    assert "Page 4, Table T4-1" in res.evidence[0].citation

    # Non-match returns None
    res_none = layer.evaluate("AMD EPYC 9654", facts)
    assert res_none is None


def test_layer2_rule_based_matching() -> None:
    layer = RuleBasedLayer()

    # Numeric >= check
    facts_storage = [
        FactItem(
            field_name="Usable Capacity",
            value="120TB usable",
            source_page=7,
        )
    ]
    res_pass = layer.evaluate("Minimum 100TB usable storage", facts_storage)
    assert res_pass is not None
    assert res_pass.state == ComplianceState.COMPLIANT
    assert res_pass.confidence == 0.95

    # Numeric failing check (120TB < required 200TB)
    res_fail = layer.evaluate("At least 200TB storage", facts_storage)
    assert res_fail is not None
    assert res_fail.state == ComplianceState.NON_COMPLIANT
    assert res_fail.confidence == 0.95

    # Redundancy check
    facts_psu = [
        FactItem(
            field_name="Power Supply",
            value="Dual 1600W hot-pluggable titanium power supplies",
            source_page=2,
        )
    ]
    res_redundancy = layer.evaluate("Redundant power supply required", facts_psu)
    assert res_redundancy is not None
    assert res_redundancy.state == ComplianceState.COMPLIANT
    assert res_redundancy.confidence == 0.92


def test_layer3_unit_conversion_matching() -> None:
    layer = UnitConversionLayer()
    facts = [
        FactItem(
            field_name="Memory",
            value="System equipped with 256 gigabytes DDR5",
            source_page=5,
        )
    ]

    # Requirement formatted as 256GB
    res = layer.evaluate("256GB DDR5", facts)
    assert res is not None
    assert res.state == ComplianceState.COMPLIANT
    assert res.confidence == 0.94
    assert res.layer_name == "unit_conversion"


def test_layer4_semantic_matching() -> None:
    layer = SemanticMatchLayer()
    facts = [
        FactItem(
            field_name="Networking",
            value="Dual-port 25GbE SFP28 network adapter card",
            source_page=6,
        )
    ]

    # Requirement uses synonyms "NIC", "ports", "interface"
    res = layer.evaluate("25GbE NIC interface", facts)
    assert res is not None
    assert res.state == ComplianceState.COMPLIANT
    assert res.confidence >= 0.70
    assert res.layer_name == "semantic_match"


@pytest.mark.asyncio
async def test_layer5_llm_reasoning_and_engine_early_exit() -> None:
    mock_llm = MockLLMProvider()
    engine = ComplianceEngine(llm_provider=mock_llm)

    # 1. Exact match should NOT call LLM (early exit)
    exact_facts = [
        FactItem(
            field_name="Model",
            value="PowerStore 5000T",
            source_page=1,
        )
    ]
    decision_exact = await engine.evaluate_requirement("PowerStore 5000T", exact_facts)
    assert decision_exact.state == ComplianceState.COMPLIANT
    assert decision_exact.resolving_layer == "exact_match"
    assert len(mock_llm.call_history) == 0  # LLM was skipped!

    # 2. Complex ambiguous requirement falls through to Layer 5 (LLM)
    mock_llm.set_responses(
        [
            json.dumps(
                {
                    "status": "COMPLIANT",
                    "confidence": 0.96,
                    "reasoning": "Firmware supports FIPS 140-3 cryptography according to certificate section.",
                    "matched_value": "FIPS 140-3 Level 2",
                    "evidence_text": "Cryptographic module certified under FIPS 140-3",
                }
            )
        ]
    )

    complex_facts = [
        FactItem(
            field_name="Security Standard",
            value="Cryptographic module certified under FIPS 140-3 Level 2 validation",
            source_page=12,
        )
    ]
    decision_llm = await engine.evaluate_requirement(
        "Shall satisfy stringent cryptographic module validation",
        complex_facts,
    )
    assert decision_llm.state == ComplianceState.COMPLIANT
    assert decision_llm.resolving_layer == "llm_reasoning"
    assert len(mock_llm.call_history) == 1  # LLM was invoked for complex case


@pytest.mark.asyncio
async def test_hallucination_prevention_not_found() -> None:
    engine = ComplianceEngine(llm_provider=MockLLMProvider())

    # Empty facts list -> returns NOT_FOUND with zero hallucinations
    decision_empty = await engine.evaluate_requirement("Must support Quantum Encryption", [])
    assert decision_empty.state == ComplianceState.NOT_FOUND
    assert decision_empty.confidence >= 0.90
    assert len(decision_empty.evidence) == 0

    # Completely unrelated facts -> NOT_FOUND
    unrelated_facts = [
        FactItem(
            field_name="Color",
            value="Black chassis paint",
            source_page=1,
        )
    ]
    decision_unrelated = await engine.evaluate_requirement("Liquid immersion cooling support", unrelated_facts)
    assert decision_unrelated.state == ComplianceState.NOT_FOUND


@pytest.mark.asyncio
async def test_conflict_detection_ambiguous() -> None:
    engine = ComplianceEngine(llm_provider=MockLLMProvider())

    # Two conflicting memory facts (128GB on page 2, 256GB on page 10)
    conflicting_facts = [
        FactItem(
            field_name="RAM Capacity",
            value="128GB DDR5",
            source_page=2,
            source_table_id="T2",
        ),
        FactItem(
            field_name="RAM Capacity",
            value="256GB DDR5",
            source_page=10,
            source_table_id="T10",
        ),
    ]

    decision = await engine.evaluate_requirement("At least 256GB RAM", conflicting_facts)
    assert decision.state == ComplianceState.AMBIGUOUS
    assert decision.resolving_layer == "conflict_resolver"
    assert len(decision.evidence) == 2
    assert len(decision.conflicting_evidence) == 2


@pytest.mark.asyncio
async def test_compliance_engine_end_to_end_multi_requirements() -> None:
    engine = ComplianceEngine(llm_provider=MockLLMProvider())

    facts_corpus = [
        FactItem(field_name="Compute", value="2x Intel Xeon Gold 6430", source_page=3),
        FactItem(field_name="Memory", value="512GB DDR5 Registered ECC", source_page=4),
        FactItem(field_name="Storage", value="150TB All-Flash NVMe", source_page=5),
        FactItem(field_name="Network", value="4x 25GbE SFP28 Ports", source_page=6),
        FactItem(field_name="Power", value="Redundant 1600W Titanium PSUs", source_page=7),
    ]

    test_requirements = [
        ("Intel Xeon Gold 6430", ComplianceState.COMPLIANT, "exact_match"),
        ("Minimum 256GB RAM", ComplianceState.COMPLIANT, "rule_based"),
        ("At least 200TB Storage", ComplianceState.NON_COMPLIANT, "rule_based"),
        ("512 gigabytes memory", ComplianceState.COMPLIANT, "unit_conversion"),
        ("Redundant power supplies", ComplianceState.COMPLIANT, "rule_based"),
        ("Immersion liquid tank required", ComplianceState.NOT_FOUND, "none"),
    ]

    for req_text, expected_state, expected_layer in test_requirements:
        dec = await engine.evaluate_requirement(req_text, facts_corpus)
        assert dec.state == expected_state, f"Failed for '{req_text}': expected {expected_state}, got {dec.state}"
        if expected_layer != "none":
            assert dec.resolving_layer == expected_layer, f"Failed resolving layer for '{req_text}'"
