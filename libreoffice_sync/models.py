from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CatalogRow:
    row_number: int
    automation_id: str
    active: str
    publish: str
    featured: str
    order: str
    update_mode: str
    product_url: str
    affiliate_url: str
    partner: str
    name: str
    description: str
    category: str
    subcategory: str
    product_type: str
    current_price: Decimal | None
    previous_price: Decimal | None
    coupon: str
    coupon_expires_at: str
    images: tuple[str, str, str, str]
    button_text: str
    row_hash: str
    acknowledged_hash: str


@dataclass(frozen=True, slots=True)
class BackendStatus:
    automation_id: str
    external_id: str
    status: str
    message: str
    discount: str
    last_published_url: str
    data_signature: str
    last_checked_at: str
    last_updated_at: str
