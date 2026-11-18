"""State and catalog records for the standalone simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class Address:
    id: str
    full_address: str
    address_line: str
    address_line2: str
    locality: str
    city: str
    postal_code: str
    category: str
    user_name: str
    user_phone: str


@dataclass(frozen=True, slots=True)
class Addon:
    id: str
    group_id: str
    name: str
    price_paise: int


@dataclass(frozen=True, slots=True)
class Variant:
    id: str
    group_id: str
    name: str
    price_delta_paise: int


@dataclass(frozen=True, slots=True)
class MenuItem:
    id: str
    restaurant_id: str
    category: str
    name: str
    description: str
    price_paise: int
    vegetarian: bool
    in_stock: bool
    dietary_tags: tuple[str, ...]
    allergens: tuple[str, ...]
    allergen_data_complete: bool
    spice_level: str
    variants: tuple[Variant, ...] = ()
    addons: tuple[Addon, ...] = ()


@dataclass(frozen=True, slots=True)
class Restaurant:
    id: str
    name: str
    area: str
    cuisines: tuple[str, ...]
    rating: float
    delivery_minutes: int
    open: bool
    menu: tuple[MenuItem, ...]


@dataclass(slots=True)
class CartSelection:
    item_id: str
    quantity: int
    variant_ids: tuple[str, ...] = ()
    addon_ids: tuple[str, ...] = ()


@dataclass(slots=True)
class Cart:
    id: str
    restaurant_id: str
    restaurant_name: str
    address_id: str
    items: dict[str, CartSelection] = field(default_factory=dict)
    coupon_code: str | None = None
    version: int = 0


@dataclass(frozen=True, slots=True)
class Order:
    id: str
    restaurant_id: str
    restaurant_name: str
    address_id: str
    lines: tuple[dict[str, object], ...]
    total_paise: int
    status: str
    created_at: datetime
    note: str = ""


@dataclass(slots=True)
class UserState:
    addresses: dict[str, Address]
    cart: Cart | None = None
    orders: dict[str, Order] = field(default_factory=dict)
    error_reports: list[dict[str, object]] = field(default_factory=list)


def now_utc() -> datetime:
    return datetime.now(UTC)
