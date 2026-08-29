import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from ai_rfp_excel.app.ai.base import (
    LLMTimeoutError,
    ModelNotAvailableError,
    OllamaUnreachableError,
    StructuredOutputValidationError,
)
from ai_rfp_excel.app.ai.mock_provider import MockLLMProvider
from ai_rfp_excel.app.ai.models import (
    AVAILABLE_MODELS,
    ChatMessage,
    ComplianceAnalysisResult,
    ComplianceStatus,
    Role,
    SpecExtractionResult,
)
from ai_rfp_excel.app.ai.prompts import (
    build_compliance_matching_prompt,
    build_evidence_synthesis_prompt,
    build_retry_error_prompt,
    build_spec_extraction_prompt,
)
from ai_rfp_excel.app.ai.provider import LocalLLMProvider, extract_json_content


def test_available_models_catalog() -> None:
    assert len(AVAILABLE_MODELS) == 5
    model_names = [m.name for m in AVAILABLE_MODELS]
    assert "Qwen 3 4B" in model_names
    assert "Qwen 2.5 3B" in model_names
    assert "Phi-3.5 Mini 3.8B" in model_names
    assert "Gemma 3 4B" in model_names
    assert "Llama 3.2 3B" in model_names

    # Check default model
    default_model = next(m for m in AVAILABLE_MODELS if m.is_default)
    assert default_model.name == "Qwen 3 4B"
    assert "2.5GB RAM" in default_model.label


@pytest.mark.asyncio
async def test_mock_llm_provider_model_listing_and_availability() -> None:
    provider = MockLLMProvider(
        available_models=["qwen3:4b", "phi3.5:3.8b"]
    )
    models = await provider.list_models()
    assert len(models) == 5

    qwen3 = next(m for m in models if m.id == "qwen3-4b")
    assert qwen3.is_available is True

    llama = next(m for m in models if m.id == "llama3.2-3b")
    assert llama.is_available is False

    assert await provider.is_model_available("qwen3:4b") is True
    assert await provider.is_model_available("llama3.2:3b") is False


@pytest.mark.asyncio
async def test_mock_llm_provider_basic_chat() -> None:
    provider = MockLLMProvider(
        responses=["Hello, I am Qwen assistant."]
    )
    response = await provider.chat(
        messages=[ChatMessage(role=Role.USER, content="Hello")]
    )
    assert response == "Hello, I am Qwen assistant."
    assert len(provider.call_history) == 1


@pytest.mark.asyncio
async def test_mock_llm_provider_structured_output_success() -> None:
    mock_data = {
        "status": "COMPLIANT",
        "confidence": 0.98,
        "reasoning": "Dual 1600W Titanium power supplies meet redundant power requirement.",
        "matched_value": "Dual 1600W Titanium PSUs",
        "evidence_text": "Spec page 4: 2x 1600W Titanium hot-plug power supplies",
    }
    provider = MockLLMProvider(
        responses=[json.dumps(mock_data)]
    )

    result = await provider.chat(
        messages=[ChatMessage(role=Role.USER, content="Evaluate compliance")],
        response_model=ComplianceAnalysisResult,
    )

    assert isinstance(result, ComplianceAnalysisResult)
    assert result.status == ComplianceStatus.COMPLIANT
    assert result.confidence == 0.98
    assert "Titanium" in result.reasoning


@pytest.mark.asyncio
async def test_mock_llm_provider_structured_output_one_retry_recovery() -> None:
    # First response is invalid JSON / schema; Second response is valid
    invalid_raw = "This is not json: status=YES"
    valid_data = {
        "status": "NON_COMPLIANT",
        "confidence": 0.95,
        "reasoning": "Memory is only 128GB, whereas 256GB is required.",
        "matched_value": "128GB DDR5",
        "evidence_text": "System equipped with 128GB RAM",
    }

    provider = MockLLMProvider(
        responses=[invalid_raw, json.dumps(valid_data)]
    )

    result = await provider.chat(
        messages=[ChatMessage(role=Role.USER, content="Evaluate memory requirement")],
        response_model=ComplianceAnalysisResult,
    )

    assert isinstance(result, ComplianceAnalysisResult)
    assert result.status == ComplianceStatus.NON_COMPLIANT
    assert result.confidence == 0.95
    assert len(provider.call_history) == 2
    assert provider.call_history[1].get("is_retry") is True


@pytest.mark.asyncio
async def test_mock_llm_provider_structured_output_retry_failure_raises() -> None:
    # Both initial and retry responses are invalid
    invalid_1 = "Bad output 1"
    invalid_2 = "Bad output 2"

    provider = MockLLMProvider(
        responses=[invalid_1, invalid_2]
    )

    with pytest.raises(StructuredOutputValidationError) as exc_info:
        await provider.chat(
            messages=[ChatMessage(role=Role.USER, content="Evaluate")],
            response_model=ComplianceAnalysisResult,
        )

    assert "ComplianceAnalysisResult" in str(exc_info.value)
    assert "Failed to validate structured output" in str(exc_info.value)


@pytest.mark.asyncio
async def test_mock_llm_provider_errors() -> None:
    # Model not available
    provider = MockLLMProvider(available_models=["qwen3:4b"])
    with pytest.raises(ModelNotAvailableError) as exc_info:
        await provider.chat(
            messages=[ChatMessage(role=Role.USER, content="Hi")],
            model="phi3.5:3.8b",
        )
    assert "phi3.5:3.8b" in str(exc_info.value)
    assert "ollama pull" in str(exc_info.value)

    # Ollama unreachable
    provider_unreachable = MockLLMProvider(simulate_unreachable=True)
    with pytest.raises(OllamaUnreachableError) as exc_info2:
        await provider_unreachable.chat(messages=[ChatMessage(role=Role.USER, content="Hi")])
    assert "Ollama is unreachable" in str(exc_info2.value)

    # Timeout
    provider_timeout = MockLLMProvider(simulate_timeout=True)
    with pytest.raises(LLMTimeoutError):
        await provider_timeout.chat(messages=[ChatMessage(role=Role.USER, content="Hi")])


@pytest.mark.asyncio
async def test_local_llm_provider_with_mocked_http() -> None:
    provider = LocalLLMProvider(base_url="http://localhost:11434")

    # Mock /api/tags and /api/chat
    tags_payload = {"models": [{"name": "qwen3:4b"}, {"name": "llama3.2:3b"}]}
    chat_payload = {
        "message": {
            "role": "assistant",
            "content": json.dumps(
                {
                    "specifications": [
                        {
                            "feature": "Processors",
                            "value": "2x Intel Xeon Gold 6430",
                            "source_snippet": "Dual Intel Xeon 6430",
                            "confidence": 1.0,
                        }
                    ],
                    "summary": "Dual Xeon processor configuration",
                }
            ),
        }
    }

    from unittest.mock import MagicMock

    mock_client = AsyncMock()
    mock_tags_resp = MagicMock(status_code=200)
    mock_tags_resp.json.return_value = tags_payload
    mock_tags_resp.raise_for_status.return_value = None

    mock_chat_resp = MagicMock(status_code=200)
    mock_chat_resp.json.return_value = chat_payload
    mock_chat_resp.raise_for_status.return_value = None

    mock_client.get.return_value = mock_tags_resp
    mock_client.post.return_value = mock_chat_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        # Check model list
        models = await provider.list_models()
        qwen = next(m for m in models if m.id == "qwen3-4b")
        assert qwen.is_available is True

        # Check structured chat
        result = await provider.chat(
            messages=[ChatMessage(role=Role.USER, content="Extract specs")],
            response_model=SpecExtractionResult,
            model="qwen3:4b",
        )

        assert isinstance(result, SpecExtractionResult)
        assert len(result.specifications) == 1
        assert result.specifications[0].feature == "Processors"
        assert result.specifications[0].value == "2x Intel Xeon Gold 6430"


@pytest.mark.asyncio
async def test_local_llm_provider_unreachable_network_error() -> None:
    provider = LocalLLMProvider(base_url="http://localhost:11434")

    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.ConnectError("Connection refused")
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(OllamaUnreachableError) as exc_info:
            await provider.list_models()
        assert "Ollama is unreachable" in str(exc_info.value)



def test_prompt_builders() -> None:
    # Spec Extraction
    spec_prompt = build_spec_extraction_prompt(
        text_content="Dual redundant 10Gbps SFP+ ports",
        page_number=3,
        table_context="Port 1: 10G, Port 2: 10G",
    )
    assert "Page 3" in spec_prompt
    assert "Dual redundant 10Gbps" in spec_prompt
    assert "Table Data:" in spec_prompt

    # Compliance Matching
    compliance_prompt = build_compliance_matching_prompt(
        requirement_text="Must have redundant cooling fans",
        extracted_facts=["Chassis includes 4 hot-swappable redundant fan modules"],
        vendor_name="Cisco",
        section_context="Hardware",
    )
    assert "vendor 'Cisco'" in compliance_prompt
    assert "Section: Hardware" in compliance_prompt
    assert "COMPLIANT" in compliance_prompt

    # Evidence Synthesis
    evidence_prompt = build_evidence_synthesis_prompt(
        requirement_text="100TB Storage",
        raw_evidence_snippets=["Array offers 120TB raw"],
        page_number=8,
        table_id="T8-1",
    )
    assert "Page 8, Table T8-1" in evidence_prompt
    assert "100TB Storage" in evidence_prompt

    # Retry Error
    retry_prompt = build_retry_error_prompt(
        previous_raw_output="bad json",
        validation_error="Field required: status",
        schema_json='{"type": "object"}',
    )
    assert "Field required: status" in retry_prompt
    assert "bad json" in retry_prompt


def test_extract_json_content_with_markdown_fences() -> None:
    raw_with_fences = '```json\n{"status": "COMPLIANT", "confidence": 0.9}\n```'
    extracted = extract_json_content(raw_with_fences)
    assert json.loads(extracted) == {"status": "COMPLIANT", "confidence": 0.9}

    plain_json = '{"key": "value"}'
    assert extract_json_content(plain_json) == '{"key": "value"}'
