"""Deterministic Bengaluru restaurant and menu catalog."""

from __future__ import annotations

from swiggy_simulator.models import Addon, MenuItem, Restaurant, Variant

AREAS = ("Indiranagar", "Koramangala", "Whitefield", "Jayanagar")
CUISINES = ("North Indian", "South Indian", "Chinese", "Italian", "Healthy", "Biryani")
RESTAURANT_NAMES = (
    "Wok This Way",
    "Green Bowl Kitchen",
    "Punjab Tandoor",
    "Dosa Junction",
    "Pasta Courtyard",
    "Royal Biryani Room",
    "Millet & More",
    "Curry Leaf Company",
    "Saffron Table",
    "Udupi Express",
    "Paneer Project",
    "The Healthy Tiffin",
)
ITEM_BASES = (
    "Vegetable Curry",
    "Paneer Pepper Fry",
    "Seasonal Salad",
    "Roasted Vegetable Wrap",
    "Dal Rice Combo",
    "Spiced Tofu Bowl",
    "Family Meal Box",
    "Chef Special",
)


def build_catalog() -> dict[str, Restaurant]:
    restaurants: dict[str, Restaurant] = {}
    for restaurant_number, name in enumerate(RESTAURANT_NAMES, start=1):
        restaurant_id = f"rest_{restaurant_number:03d}"
        cuisine = CUISINES[(restaurant_number - 1) % len(CUISINES)]
        area = AREAS[(restaurant_number - 1) % len(AREAS)]
        menu: list[MenuItem] = []
        for item_number, base in enumerate(ITEM_BASES, start=1):
            item_id = f"{restaurant_id}_item_{item_number:02d}"
            vegetarian = item_number != 8
            variants = (
                Variant(f"{item_id}_regular", "size", "Regular", 0),
                Variant(f"{item_id}_large", "size", "Large", 5_000),
            )
            addons = (
                Addon(f"{item_id}_extra", "extras", "Extra portion", 3_000),
                Addon(f"{item_id}_drink", "extras", "Lime drink", 2_500),
            )
            menu.append(
                MenuItem(
                    id=item_id,
                    restaurant_id=restaurant_id,
                    category=("Recommended", "Mains", "Healthy", "Combos")[(item_number - 1) % 4],
                    name=f"{cuisine} {base}",
                    description=f"Freshly prepared {base.casefold()} from {name}.",
                    price_paise=10_000 + restaurant_number * 250 + item_number * 1_000,
                    vegetarian=vegetarian,
                    in_stock=not (restaurant_number == 1 and item_number == 8),
                    dietary_tags=("vegetarian",) if vegetarian else (),
                    allergens=("milk",) if "Paneer" in base else ("wheat",),
                    allergen_data_complete=not (restaurant_number == 3 and item_number == 3),
                    spice_level=("mild", "medium", "spicy")[(item_number - 1) % 3],
                    variants=variants if item_number in {2, 7} else (),
                    addons=addons if item_number in {2, 4, 7} else (),
                )
            )
        restaurants[restaurant_id] = Restaurant(
            id=restaurant_id,
            name=name,
            area=area,
            cuisines=(cuisine,),
            rating=round(3.8 + (restaurant_number % 10) * 0.1, 1),
            delivery_minutes=20 + (restaurant_number % 6) * 5,
            open=restaurant_number != 12,
            menu=tuple(menu),
        )
    return restaurants
