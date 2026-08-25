import pytest
import pytest_asyncio

from app.ai.output_parser import StructuredOutputParser, ComplianceResult
from app.ai.mock_llm import MockLLMProvider


@pytest.mark.asyncio
async def test_parse_valid_json():
    llm = MockLLMProvider()
    llm.set_default_response('{"status": "COMPLIANT", "confidence": 0.95, "evidence": [], "reasoning": "test"}')

    parser = StructuredOutputParser(llm)
    result = await parser.parse_with_retry(
        model="qwen3:4b",
        messages=[{"role": "user", "content": "Test"}],
        output_model=ComplianceResult,
    )

    assert result is not None
    assert result.status == "COMPLIANT"
    assert result.confidence == 0.95


@pytest.mark.asyncio
async def test_parse_invalid_json_retry():
    llm = MockLLMProvider()
    llm.set_default_response("This is not JSON")

    parser = StructuredOutputParser(llm)
    result = await parser.parse_with_retry(
        model="qwen3:4b",
        messages=[{"role": "user", "content": "Test"}],
        output_model=ComplianceResult,
        max_retries=1,
    )

    assert result is None


@pytest.mark.asyncio
async def test_parse_json_in_markdown():
    llm = MockLLMProvider()
    llm.set_default_response('Here is the result:\n```json\n{"status": "COMPLIANT", "confidence": 0.9, "evidence": [], "reasoning": "test"}\n```')

    parser = StructuredOutputParser(llm)
    result = await parser.parse_with_retry(
        model="qwen3:4b",
        messages=[{"role": "user", "content": "Test"}],
        output_model=ComplianceResult,
    )

    assert result is not None
    assert result.status == "COMPLIANT"


@pytest.mark.asyncio
async def test_parse_adds_error_context():
    llm = MockLLMProvider()
    llm.set_default_response("Invalid JSON")

    parser = StructuredOutputParser(llm)
    result = await parser.parse_with_retry(
        model="qwen3:4b",
        messages=[{"role": "user", "content": "Test"}],
        output_model=ComplianceResult,
        max_retries=1,
    )

    assert llm.call_count == 2
    assert "validation error" in llm.calls[1]["messages"][-1]["content"].lower()
