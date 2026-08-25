import pytest
import pytest_asyncio

from app.ai.mock_llm import MockLLMProvider


@pytest.mark.asyncio
async def test_mock_llm_chat():
    llm = MockLLMProvider()
    llm.set_default_response('{"status": "COMPLIANT", "confidence": 0.95}')

    response = await llm.chat(
        model="qwen3:4b",
        messages=[{"role": "user", "content": "Test prompt"}],
    )

    assert response.content == '{"status": "COMPLIANT", "confidence": 0.95}'
    assert response.model == "qwen3:4b"
    assert response.done is True
    assert llm.call_count == 1


@pytest.mark.asyncio
async def test_mock_llm_model_specific_response():
    llm = MockLLMProvider()
    llm.set_response("qwen3:4b", '{"result": "qwen response"}')
    llm.set_response("llama3.2:3b", '{"result": "llama response"}')

    response1 = await llm.chat(
        model="qwen3:4b",
        messages=[{"role": "user", "content": "Test"}],
    )
    response2 = await llm.chat(
        model="llama3.2:3b",
        messages=[{"role": "user", "content": "Test"}],
    )

    assert response1.content == '{"result": "qwen response"}'
    assert response2.content == '{"result": "llama response"}'


@pytest.mark.asyncio
async def test_mock_llm_is_model_available():
    llm = MockLLMProvider()

    assert await llm.is_model_available("qwen3:4b")
    assert await llm.is_model_available("any-model")


@pytest.mark.asyncio
async def test_mock_llm_list_models():
    llm = MockLLMProvider()

    models = await llm.list_models()
    assert len(models) == 5
    assert any(m["name"] == "qwen3:4b" for m in models)


@pytest.mark.asyncio
async def test_mock_llm_tracks_calls():
    llm = MockLLMProvider()

    await llm.chat(model="qwen3:4b", messages=[{"role": "user", "content": "Test 1"}])
    await llm.chat(model="llama3.2:3b", messages=[{"role": "user", "content": "Test 2"}])

    assert llm.call_count == 2
    assert len(llm.calls) == 2
    assert llm.calls[0]["model"] == "qwen3:4b"
    assert llm.calls[1]["model"] == "llama3.2:3b"


@pytest.mark.asyncio
async def test_mock_llm_reset():
    llm = MockLLMProvider()

    await llm.chat(model="qwen3:4b", messages=[{"role": "user", "content": "Test"}])
    assert llm.call_count == 1

    llm.reset()
    assert llm.call_count == 0
    assert len(llm.calls) == 0
