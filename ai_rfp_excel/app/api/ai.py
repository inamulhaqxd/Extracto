from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ai_rfp_excel.app.ai.base import OllamaUnreachableError
from ai_rfp_excel.app.ai.models import AVAILABLE_MODELS, ModelInfo, ModelPreference
from ai_rfp_excel.app.ai.provider import LocalLLMProvider
from ai_rfp_excel.app.api.deps import get_current_user
from ai_rfp_excel.app.config import settings
from ai_rfp_excel.app.database.connection import get_db
from ai_rfp_excel.app.database.models import User

router = APIRouter(prefix="/ai", tags=["ai"])
llm_provider = LocalLLMProvider()


class ModelsListResponse(BaseModel):
    models: list[ModelInfo]
    default_model: str
    ollama_reachable: bool
    warning: str | None = None


@router.get("/models", response_model=ModelsListResponse)
async def list_available_models(
    current_user: User = Depends(get_current_user),
) -> ModelsListResponse:
    """List 5 supported local models with their availability status in Ollama."""
    try:
        models = await llm_provider.list_models()
        return ModelsListResponse(
            models=models,
            default_model=settings.DEFAULT_LLM_MODEL,
            ollama_reachable=True,
            warning=None,
        )
    except OllamaUnreachableError:
        # Gracefully return model catalog with is_available=False and warning
        models = [
            ModelInfo(
                id=m.id,
                name=m.name,
                tag=m.tag,
                label=m.label,
                ram_usage=m.ram_usage,
                context_length=m.context_length,
                is_default=m.is_default,
                is_available=False,
            )
            for m in AVAILABLE_MODELS
        ]
        return ModelsListResponse(
            models=models,
            default_model=settings.DEFAULT_LLM_MODEL,
            ollama_reachable=False,
            warning=f"Ollama is unreachable at {settings.OLLAMA_BASE_URL}. Ensure Ollama is running.",
        )


@router.get("/preference", response_model=ModelPreference)
async def get_user_model_preference(
    current_user: User = Depends(get_current_user),
) -> ModelPreference:
    """Get the current user's default LLM model preference."""
    meta = current_user.metadata_json if hasattr(current_user, "metadata_json") and current_user.metadata_json else {}
    if not isinstance(meta, dict):
        meta = {}

    preferred_tag = meta.get("preferred_llm_model", settings.DEFAULT_LLM_MODEL)
    model_name = next((m.name for m in AVAILABLE_MODELS if m.tag == preferred_tag), preferred_tag)

    return ModelPreference(model_tag=preferred_tag, model_name=model_name)


@router.put("/preference", response_model=ModelPreference)
async def update_user_model_preference(
    preference: ModelPreference,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ModelPreference:
    """Save the user's selected LLM model preference in database."""
    # Validate that the selected model tag exists in available models
    matched = next((m for m in AVAILABLE_MODELS if m.tag == preference.model_tag or m.id == preference.model_tag), None)
    if not matched:
        valid_tags = [m.tag for m in AVAILABLE_MODELS]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model tag '{preference.preference_tag if hasattr(preference, 'preference_tag') else preference.model_tag}'. Supported models: {', '.join(valid_tags)}",
        )

    # Update user's metadata
    meta: dict[str, Any] = dict(current_user.metadata_json) if hasattr(current_user, "metadata_json") and current_user.metadata_json else {}
    meta["preferred_llm_model"] = matched.tag
    if hasattr(current_user, "metadata_json"):
        current_user.metadata_json = meta
        db.add(current_user)
        await db.flush()

    return ModelPreference(model_tag=matched.tag, model_name=matched.name)
