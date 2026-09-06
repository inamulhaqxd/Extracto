from enum import Enum

from pydantic import BaseModel, Field


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    role: Role = Role.USER
    content: str


class ModelInfo(BaseModel):
    model_config = {"protected_namespaces": ()}
    id: str
    name: str
    tag: str
    label: str
    ram_usage: str
    context_length: str
    is_default: bool = False
    is_available: bool = False



AVAILABLE_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="qwen3-8b",
        name="Qwen 3 8B",
        tag="qwen3:8b",
        label="Qwen 3 8B — 5GB RAM, 262K context",
        ram_usage="5GB",
        context_length="262K",
        is_default=False,
    ),
    ModelInfo(
        id="qwen3-4b",
        name="Qwen 3 4B",
        tag="qwen3:4b",
        label="Qwen 3 4B — 2.5GB RAM, 262K context",
        ram_usage="2.5GB",
        context_length="262K",
        is_default=True,
    ),
    ModelInfo(
        id="qwen2.5-3b",
        name="Qwen 2.5 3B",
        tag="qwen2.5:3b",
        label="Qwen 2.5 3B — 1.9GB RAM, 128K context",
        ram_usage="1.9GB",
        context_length="128K",
        is_default=False,
    ),
    ModelInfo(
        id="phi3.5-mini-3.8b",
        name="Phi-3.5 Mini 3.8B",
        tag="phi3.5:3.8b",
        label="Phi-3.5 Mini 3.8B — 2.2GB RAM, 128K context",
        ram_usage="2.2GB",
        context_length="128K",
        is_default=False,
    ),
    ModelInfo(
        id="gemma3-4b",
        name="Gemma 3 4B",
        tag="gemma3:4b",
        label="Gemma 3 4B — 2.5GB RAM, 8K context",
        ram_usage="2.5GB",
        context_length="8K",
        is_default=False,
    ),
    ModelInfo(
        id="qwen2.5-1.5b",
        name="Qwen 2.5 1.5B",
        tag="qwen2.5:1.5b",
        label="Qwen 2.5 1.5B — 980MB RAM, 128K context",
        ram_usage="980MB",
        context_length="128K",
        is_default=False,
    ),
    ModelInfo(
        id="llama3.2-3b",
        name="Llama 3.2 3B",
        tag="llama3.2:3b",
        label="Llama 3.2 3B — 2.0GB RAM, 128K context",
        ram_usage="2.0GB",
        context_length="128K",
        is_default=False,
    ),
]


class ModelPreference(BaseModel):
    model_config = {"protected_namespaces": ()}
    model_tag: str
    model_name: str | None = None



# --- Structured Output Schemas ---


class ExtractedSpecItem(BaseModel):
    feature: str = Field(description="Name or category of the technical specification")
    value: str = Field(description="Extracted value, constraint, or requirement detail")
    source_snippet: str | None = Field(default=None, description="Exact text quotation from source")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")


class SpecExtractionResult(BaseModel):
    specifications: list[ExtractedSpecItem] = Field(default_factory=list)
    summary: str | None = None


class ComplianceStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    PARTIAL = "PARTIAL"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_SPECIFIED = "NOT SPECIFIED"
    NOT_APPLICABLE = "NOT APPLICABLE"


class ComplianceAnalysisResult(BaseModel):
    status: ComplianceStatus
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    matched_value: str | None = None
    evidence_text: str | None = None
    structured_constraints: dict[str, object] | None = None


class EvidenceResult(BaseModel):
    requirement_id: str | None = None
    evidence_text: str
    page_reference: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
