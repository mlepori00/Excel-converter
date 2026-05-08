"""JSON-ready contracts for the future AMP Sport UI.

These dataclasses intentionally do not depend on FastAPI, Pydantic, Streamlit, or React.
They define the shape that the new UI can rely on while the existing backend stays intact.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any


class StringEnum(str, Enum):
    """Enum that serializes naturally as a string value."""


class WorkflowStep(StringEnum):
    """The guided converter workflow steps."""

    PREPARE_FILE = "prepare_file"
    RECOGNIZE_PRODUCTS = "recognize_products"
    REVIEW_PRICES = "review_prices"
    EXPORT_OFFER = "export_offer"


class RequirementStatus(StringEnum):
    """UI status for required and optional checklist items."""

    OK = "ok"
    MISSING = "missing"
    OPTIONAL = "optional"
    WARNING = "warning"


class ExtractionMode(StringEnum):
    """How product extraction was or should be performed."""

    LOCAL = "local"
    CACHE = "cache"
    API = "api"
    NOT_READY = "not_ready"


@dataclass(frozen=True)
class Requirement:
    """One right-rail checklist item."""

    key: str
    label: str
    description: str
    status: RequirementStatus
    required: bool = True


@dataclass(frozen=True)
class WorkflowStepInfo:
    """Visible metadata for a workflow stepper item."""

    step: WorkflowStep
    index: int
    label: str
    description: str
    active: bool = False
    completed: bool = False


@dataclass(frozen=True)
class FileMetadata:
    """Metadata shown after a supplier file has been read."""

    filename: str
    size_bytes: int
    sheet_names: list[str] = field(default_factory=list)
    recommended_sheet: str | None = None
    selected_sheet: str | None = None
    row_count: int = 0
    column_count: int = 0
    detected_currency: str | None = None
    layout_type: str | None = None
    was_unpivoted: bool = False
    unpivot_info: str = ""
    column_mapping: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PrepareFileState:
    """State for screen 1: Datei vorbereiten."""

    supplier_name: str
    selected_profile: str | None
    file: FileMetadata | None
    requirements: list[Requirement]
    can_continue: bool


@dataclass(frozen=True)
class SanitizerState:
    """Visible sanitizer state before any API call."""

    active: bool
    removed_items: int
    log: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExtractionState:
    """State for screen 2: Produkte erkennen."""

    mode: ExtractionMode
    product_count: int
    sanitizer: SanitizerState
    api_estimated_cost_chf: float | None = None
    api_requires_confirmation: bool = True
    can_continue: bool = False
    message: str = ""


@dataclass(frozen=True)
class ProductRow:
    """One normalized product row for the new UI table."""

    row_id: int
    sku: str | None = None
    ean: str | None = None
    product_name: str | None = None
    size: str | None = None
    color: str | None = None
    category: str | None = None
    unit_price: float | None = None
    currency: str | None = None
    ordered_qty: int | None = None
    available_qty: int | None = None
    discount_pct: float | None = None
    notes: str | None = None
    status: RequirementStatus = RequirementStatus.OK


@dataclass(frozen=True)
class PricingControls:
    """Current pricing toolbar values."""

    margin_pct: float
    target_currency: str
    market_discount_pct: float | None = None


@dataclass(frozen=True)
class PricingSummary:
    """Right-rail summary for screen 3: Preise prüfen."""

    product_count: int
    missing_qty_count: int
    missing_price_count: int
    unknown_currency_count: int
    ek_total: float | None
    vk_total: float | None
    average_margin_pct: float | None
    target_currency: str
    can_continue: bool


@dataclass(frozen=True)
class ExportPreview:
    """State for screen 4: Export erstellen."""

    supplier_name: str
    created_by: str
    target_currency: str
    valid_days: int
    product_count: int
    filename: str
    requirements: list[Requirement]
    can_download: bool


@dataclass(frozen=True)
class WorkflowState:
    """Top-level converter state consumed by the frontend shell."""

    active_step: WorkflowStep
    steps: list[WorkflowStepInfo]
    prepare_file: PrepareFileState | None = None
    extraction: ExtractionState | None = None
    pricing: PricingSummary | None = None
    export: ExportPreview | None = None


def to_jsonable(value: Any) -> Any:
    """Convert schema objects into plain JSON-ready Python values."""
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [to_jsonable(item) for item in value]
    return value

