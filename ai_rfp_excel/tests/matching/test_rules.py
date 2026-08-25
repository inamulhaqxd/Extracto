import pytest

from app.matching.rules import (
    ComplianceStatus,
    ExactMatcher,
    RuleMatcher,
    UnitConversionMatcher,
    UnitConverter,
)


def test_exact_match():
    matcher = ExactMatcher()
    decision = matcher.match("Minimum 32 cores", "Minimum 32 cores")

    assert decision is not None
    assert decision.status == ComplianceStatus.COMPLIANT
    assert decision.confidence == 1.0


def test_exact_no_match():
    matcher = ExactMatcher()
    decision = matcher.match("Minimum 32 cores", "Minimum 64 cores")

    assert decision is None


def test_rule_match_compliant():
    matcher = RuleMatcher()
    decision = matcher.match("Minimum 32 cores", "32 cores per controller")

    assert decision is not None
    assert decision.status == ComplianceStatus.COMPLIANT


def test_rule_match_non_compliant():
    matcher = RuleMatcher()
    decision = matcher.match("Minimum 64 cores", "32 cores per controller")

    assert decision is not None
    assert decision.status == ComplianceStatus.NON_COMPLIANT


def test_unit_conversion_storage():
    converter = UnitConverter()

    assert converter.are_equivalent("64 GB", "64GB", "storage")
    assert converter.are_equivalent("1 TB", "1000 GB", "storage")
    assert not converter.are_equivalent("1 TB", "500 GB", "storage")


def test_unit_conversion_memory():
    converter = UnitConverter()

    assert converter.are_equivalent("64 GB", "65536 MB", "memory")
    assert not converter.are_equivalent("1 TB", "500 GB", "memory")


def test_unit_matcher_compliant():
    matcher = UnitConversionMatcher()
    decision = matcher.match("Minimum 350 TB", "400 TB")

    assert decision is not None
    assert decision.status == ComplianceStatus.COMPLIANT


def test_unit_matcher_non_compliant():
    matcher = UnitConversionMatcher()
    decision = matcher.match("Minimum 350 TB", "300 TB")

    assert decision is not None
    assert decision.status == ComplianceStatus.NON_COMPLIANT


def test_unit_matcher_partial():
    matcher = UnitConversionMatcher()
    decision = matcher.match("Minimum 350 TB", "330 TB")

    assert decision is not None
    assert decision.status == ComplianceStatus.PARTIALLY_COMPLIANT
