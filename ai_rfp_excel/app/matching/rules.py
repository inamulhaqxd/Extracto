import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ComplianceStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    PARTIALLY_COMPLIANT = "PARTIALLY_COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    NOT_FOUND = "NOT_FOUND"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass
class Evidence:
    value: str
    page: Optional[int] = None
    table_id: Optional[str] = None
    image_id: Optional[str] = None
    source_type: str = "text"
    confidence: float = 0.0


@dataclass
class ComplianceDecision:
    status: ComplianceStatus
    confidence: float
    evidence: list[Evidence] = field(default_factory=list)
    reasoning: str = ""
    layer: str = ""


class UnitConverter:
    UNITS = {
        "storage": {
            "tb": 1000000000000,
            "gb": 1000000000,
            "mb": 1000000,
            "kb": 1000,
            "bytes": 1,
        },
        "memory": {
            "tb": 1099511627776,
            "gb": 1073741824,
            "mb": 1048576,
            "kb": 1024,
            "bytes": 1,
        },
        "frequency": {
            "ghz": 1000000000,
            "mhz": 1000000,
        },
    }

    def normalize(self, value: str, unit_type: str = "storage") -> Optional[float]:
        match = re.search(r"([\d.]+)\s*(tb|gb|mb|kb|bytes|ghz|mhz)", value.lower())
        if not match:
            return None

        number = float(match.group(1))
        unit = match.group(2)

        units = self.UNITS.get(unit_type, self.UNITS["storage"])
        if unit in units:
            return number * units[unit]

        return None

    def are_equivalent(self, value1: str, value2: str, unit_type: str = "storage") -> bool:
        norm1 = self.normalize(value1, unit_type)
        norm2 = self.normalize(value2, unit_type)

        if norm1 is None or norm2 is None:
            return False

        return abs(norm1 - norm2) < 0.001


class ExactMatcher:
    def match(self, requirement: str, reference: str) -> Optional[ComplianceDecision]:
        req_lower = requirement.lower().strip()
        ref_lower = reference.lower().strip()

        if req_lower == ref_lower:
            return ComplianceDecision(
                status=ComplianceStatus.COMPLIANT,
                confidence=1.0,
                reasoning="Exact match found",
                layer="exact",
            )

        return None


class RuleMatcher:
    OPERATORS = {
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b,
        "<": lambda a, b: a < b,
        "=": lambda a, b: abs(a - b) < 0.001,
        "==": lambda a, b: abs(a - b) < 0.001,
    }

    def match(self, requirement: str, reference: str) -> Optional[ComplianceDecision]:
        req_match = re.search(r"([\d.]+)\s*(tb|gb|mb|kb|cores?|ghz|mhz)", requirement.lower())
        ref_match = re.search(r"([\d.]+)\s*(tb|gb|mb|kb|cores?|ghz|mhz)", reference.lower())

        if not req_match or not ref_match:
            return None

        req_value = float(req_match.group(1))
        ref_value = float(ref_match.group(1))

        operator = "="
        for op in [">=", "<=", ">", "<", "=="]:
            if op in requirement:
                operator = op
                break

        op_func = self.OPERATORS.get(operator)
        if not op_func:
            return None

        is_compliant = op_func(ref_value, req_value)

        if is_compliant:
            status = ComplianceStatus.COMPLIANT
            confidence = 0.95
        elif operator in [">=", ">"] and ref_value >= req_value * 0.9:
            status = ComplianceStatus.PARTIALLY_COMPLIANT
            confidence = 0.8
        else:
            status = ComplianceStatus.NON_COMPLIANT
            confidence = 0.9

        return ComplianceDecision(
            status=status,
            confidence=confidence,
            reasoning=f"Rule-based comparison: {ref_value} {operator} {req_value}",
            layer="rules",
        )


class UnitConversionMatcher:
    def __init__(self):
        self.converter = UnitConverter()

    def match(self, requirement: str, reference: str) -> Optional[ComplianceDecision]:
        unit_type = self._detect_unit_type(requirement)
        if not unit_type:
            return None

        req_value = self.converter.normalize(requirement, unit_type)
        ref_value = self.converter.normalize(reference, unit_type)

        if req_value is None or ref_value is None:
            return None

        if self.converter.are_equivalent(requirement, reference, unit_type):
            return ComplianceDecision(
                status=ComplianceStatus.COMPLIANT,
                confidence=0.95,
                reasoning=f"Unit conversion match: {requirement} = {reference}",
                layer="unit_conversion",
            )

        if ref_value >= req_value:
            return ComplianceDecision(
                status=ComplianceStatus.COMPLIANT,
                confidence=0.9,
                reasoning=f"Value meets requirement after conversion: {ref_value} >= {req_value}",
                layer="unit_conversion",
            )
        elif ref_value >= req_value * 0.9:
            return ComplianceDecision(
                status=ComplianceStatus.PARTIALLY_COMPLIANT,
                confidence=0.8,
                reasoning=f"Value partially meets requirement: {ref_value} ~= {req_value}",
                layer="unit_conversion",
            )
        else:
            return ComplianceDecision(
                status=ComplianceStatus.NON_COMPLIANT,
                confidence=0.9,
                reasoning=f"Value below requirement: {ref_value} < {req_value}",
                layer="unit_conversion",
            )

    def _detect_unit_type(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        if any(unit in text_lower for unit in ["tb", "gb", "mb", "kb"]):
            if any(word in text_lower for word in ["ram", "memory", "ddr"]):
                return "memory"
            return "storage"
        if any(unit in text_lower for unit in ["ghz", "mhz"]):
            return "frequency"
        return None
