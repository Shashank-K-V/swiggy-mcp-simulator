"""Stateful food-delivery simulation independent from MAV."""

from __future__ import annotations

import threading
import uuid
from dataclasses import replace
from typing import Any

from swiggy_simulator.catalog import build_catalog
from swiggy_simulator.models import Address, Cart, CartSelection, Order, UserState, now_utc


class SimError(Exception):
    def __init__(self, message: str, code: str = "INVALID_REQUEST") -> None:
        super().__init__(message)
        self.code = code


def _money(paise: int) -> float:
    return round(paise / 100, 2)


class SwiggyFoodService:
    """In-memory, multi-user simulation of the non-payment Swiggy Food journey."""

    ORDER_STATUSES = ("PLACED", "CONFIRMED", "PREPARING", "PICKED_UP", "DELIVERED")

    def __init__(self) -> None:
        self.catalog = build_catalog()
        self._users: dict[str, UserState] = {}
        self._lock = threading.RLock()

    def reset(self) -> None:
        with self._lock:
            self._users.clear()

    def _user(self, user_id: str) -> UserState:
        safe_user = user_id.strip() or "demo-user"
        if safe_user not in self._users:
            self._users[safe_user] = UserState(
                addresses={
                    "addr_home": Address(
                        "addr_home",
                        "100 Simulation Road, Indiranagar, Bengaluru 560038",
                        "100 Simulation Road",
                        "Near Metro Station",
                        "Indiranagar",
                        "Bengaluru",
                        "560038",
                        "Home",
                        "MAV Demo User",
                        "9000000000",
                    ),
                    "addr_work": Address(
                        "addr_work",
                        "22 Test Park, Koramangala, Bengaluru 560034",
                        "22 Test Park",
                        "Block B",
                        "Koramangala",
                        "Bengaluru",
                        "560034",
                        "Work",
                        "MAV Demo User",
                        "9000000000",
                    ),
                }
            )
        return self._users[safe_user]

    @staticmethod
    def _address_data(address: Address) -> dict[str, Any]:
        return {
            "id": address.id,
            "fullAddress": address.full_address,
            "addressLine": address.address_line,
            "addressLine2": address.address_line2,
            "locality": address.locality,
            "city": address.city,
            "postalCode": address.postal_code,
            "addressCategory": address.category,
            "userName": address.user_name,
            "userPhone": address.user_phone,
        }

    def _address(self, state: UserState, address_id: str) -> Address:
        address = state.addresses.get(address_id)
        if address is None:
            raise SimError(f"Unknown addressId: {address_id}", "ADDRESS_NOT_FOUND")
        return address

    def create_address(self, user_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        required = ("fullAddress", "addressLine", "city", "postalCode", "userName", "userPhone")
        missing = [name for name in required if not str(arguments.get(name, "")).strip()]
        if missing:
            raise SimError(f"Missing address fields: {', '.join(missing)}")
        with self._lock:
            state = self._user(user_id)
            address_id = f"addr_{uuid.uuid4().hex[:10]}"
            address = Address(
                id=address_id,
                full_address=str(arguments["fullAddress"]).strip(),
                address_line=str(arguments["addressLine"]).strip(),
                address_line2=str(arguments.get("addressLine2", "")).strip(),
                locality=str(arguments.get("locality", "Indiranagar")).strip(),
                city=str(arguments["city"]).strip(),
                postal_code=str(arguments["postalCode"]).strip(),
                category=str(arguments.get("addressCategory", "Other")).strip(),
                user_name=str(arguments["userName"]).strip(),
                user_phone=str(arguments["userPhone"]).strip(),
            )
            state.addresses[address_id] = address
            return {"address": self._address_data(address)}

    def delete_address(self, user_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        address_id = str(arguments.get("addressId", ""))
        with self._lock:
            state = self._user(user_id)
            self._address(state, address_id)
            if state.cart and state.cart.address_id == address_id:
                raise SimError(
                    "Cannot delete the address used by the active cart", "ADDRESS_IN_USE"
                )
            del state.addresses[address_id]
            return {"deleted": True, "addressId": address_id}

    def get_addresses(self, user_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        state = self._user(user_id)
        addresses = [self._address_data(value) for value in state.addresses.values()]
        default_id = addresses[0]["id"] if addresses else None
        return {
            "addresses": addresses,
            "resolution": {
                "defaultAddressId": default_id,
                "resolutionSource": "simulated_saved_address",
                "needsUserClarification": not bool(default_id),
                "candidateAddressIds": [item["id"] for item in addresses],
            },
            "pagination": {"page": 1, "pageSize": 50, "total": len(addresses), "hasMore": False},
        }

    @staticmethod
    def _restaurant_data(restaurant: Any) -> dict[str, Any]:
        return {
            "id": restaurant.id,
            "name": restaurant.name,
            "areaName": restaurant.area,
            "cuisines": list(restaurant.cuisines),
            "avgRating": restaurant.rating,
            "deliveryTimeMinutes": restaurant.delivery_minutes,
            "availabilityStatus": "OPEN" if restaurant.open else "CLOSED",
        }

    @staticmethod
    def _item_data(item: Any) -> dict[str, Any]:
        return {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "category": item.category,
            "price": _money(item.price_paise),
            "inStock": item.in_stock,
            "isVeg": item.vegetarian,
            "dietaryTags": list(item.dietary_tags),
            "allergens": list(item.allergens),
            "allergenDataComplete": item.allergen_data_complete,
            "spiceLevel": item.spice_level,
            "variants": [
                {
                    "id": value.id,
                    "groupId": value.group_id,
                    "name": value.name,
                    "priceDelta": _money(value.price_delta_paise),
                }
                for value in item.variants
            ],
            "addons": [
                {
                    "id": value.id,
                    "groupId": value.group_id,
                    "name": value.name,
                    "price": _money(value.price_paise),
                }
                for value in item.addons
            ],
        }

    def search_restaurants(self, user_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        state = self._user(user_id)
        address = self._address(state, str(arguments.get("addressId", "")))
        query = str(arguments.get("query", "")).casefold().strip()
        matches = []
        for restaurant in self.catalog.values():
            searchable = " ".join((restaurant.name, *restaurant.cuisines)).casefold()
            if restaurant.area.casefold() == address.locality.casefold() and (
                not query or query in searchable
            ):
                matches.append(self._restaurant_data(restaurant))
        return {"restaurants": matches, "query": query, "hasMore": False}

    def _restaurant(self, restaurant_id: str) -> Any:
        restaurant = self.catalog.get(restaurant_id)
        if restaurant is None:
            raise SimError(f"Unknown restaurantId: {restaurant_id}", "RESTAURANT_NOT_FOUND")
        return restaurant

    def _item(self, restaurant_id: str, item_id: str) -> Any:
        restaurant = self._restaurant(restaurant_id)
        item = next((value for value in restaurant.menu if value.id == item_id), None)
        if item is None:
            raise SimError(f"Item {item_id} is not in restaurant {restaurant_id}", "ITEM_NOT_FOUND")
        return item

    def get_restaurant_menu(self, user_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        state = self._user(user_id)
        self._address(state, str(arguments.get("addressId", "")))
        restaurant = self._restaurant(str(arguments.get("restaurantId", "")))
        categories: dict[str, list[dict[str, Any]]] = {}
        for item in restaurant.menu:
            categories.setdefault(item.category, []).append(self._item_data(item))
        return {
            "restaurantId": restaurant.id,
            "restaurantName": restaurant.name,
            "categories": [{"name": name, "items": items} for name, items in categories.items()],
            "page": 1,
            "pageSize": len(restaurant.menu),
            "hasMore": False,
        }

    def search_menu(self, user_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        state = self._user(user_id)
        self._address(state, str(arguments.get("addressId", "")))
        query = str(arguments.get("query", "")).casefold().strip()
        if not query:
            raise SimError("query is required")
        restaurant_id = str(arguments.get("restaurantId", "")).strip()
        restaurants = [self._restaurant(restaurant_id)] if restaurant_id else self.catalog.values()
        results = []
        for restaurant in restaurants:
            for item in restaurant.menu:
                if query in f"{item.name} {item.description} {item.category}".casefold():
                    results.append(
                        {
                            "restaurant": self._restaurant_data(restaurant),
                            "item": self._item_data(item),
                        }
                    )
        return {"items": results[:50], "hasMore": len(results) > 50}

    def fetch_food_coupons(self, user_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self._user(user_id)
        return {
            "coupons": [
                {"code": "SIM50", "description": "Rs 50 off above Rs 300", "minimumOrder": 300},
                {
                    "code": "VEG20",
                    "description": "20% off up to Rs 100 above Rs 200",
                    "minimumOrder": 200,
                },
            ]
        }

    def _selection_total(self, restaurant_id: str, selection: CartSelection) -> tuple[int, Any]:
        item = self._item(restaurant_id, selection.item_id)
        if not item.in_stock:
            raise SimError(f"{item.name} is out of stock", "ITEM_UNAVAILABLE")
        variant_map = {value.id: value for value in item.variants}
        addon_map = {value.id: value for value in item.addons}
        try:
            unit = item.price_paise + sum(
                variant_map[value].price_delta_paise for value in selection.variant_ids
            )
            unit += sum(addon_map[value].price_paise for value in selection.addon_ids)
        except KeyError as exc:
            raise SimError(
                f"Invalid customization id: {exc.args[0]}", "INVALID_CUSTOMIZATION"
            ) from exc
        return unit * selection.quantity, item

    def _cart_data(self, state: UserState) -> dict[str, Any]:
        cart = state.cart
        if cart is None:
            return {"cart_id": None, "items": [], "pricing": {"to_pay": 0}, "version": 0}
        restaurant = self._restaurant(cart.restaurant_id)
        lines = []
        item_total = 0
        for selection in cart.items.values():
            line_total, item = self._selection_total(cart.restaurant_id, selection)
            item_total += line_total
            unit = line_total // selection.quantity
            lines.append(
                {
                    "menu_item_id": item.id,
                    "name": item.name,
                    "quantity": selection.quantity,
                    "final_price": _money(unit),
                    "subtotal": _money(line_total),
                    "total": _money(line_total),
                    "in_stock": item.in_stock,
                    "dietaryTags": list(item.dietary_tags),
                    "allergens": list(item.allergens),
                    "allergenDataComplete": item.allergen_data_complete,
                    "variantIds": list(selection.variant_ids),
                    "addonIds": list(selection.addon_ids),
                }
            )
        delivery = 0 if item_total >= 30_000 or not lines else 4_000
        taxes = round(item_total * 0.05)
        discount = 0
        if cart.coupon_code == "SIM50" and item_total >= 30_000:
            discount = 5_000
        elif cart.coupon_code == "VEG20" and item_total >= 20_000:
            discount = min(10_000, round(item_total * 0.2))
        total = max(0, item_total + delivery + taxes - discount)
        return {
            "addressId": cart.address_id,
            "cart_id": cart.id,
            "restaurant": {"id": restaurant.id, "name": restaurant.name},
            "items": lines,
            "pricing": {
                "item_total": _money(item_total),
                "delivery_charge": _money(delivery),
                "taxes_and_charges": _money(taxes),
                "discount": _money(discount),
                "to_pay": _money(total),
            },
            "couponCode": cart.coupon_code,
            "availablePaymentMethods": ["Cash"],
            "version": cart.version,
        }

    def update_food_cart(self, user_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._user(user_id)
            address_id = str(arguments.get("addressId", ""))
            self._address(state, address_id)
            restaurant_id = str(arguments.get("restaurantId", ""))
            restaurant = self._restaurant(restaurant_id)
            if not restaurant.open:
                raise SimError(f"{restaurant.name} is closed", "RESTAURANT_CLOSED")
            selections: dict[str, CartSelection] = {}
            for raw in arguments.get("cartItems", []):
                item_id = str(raw.get("menu_item_id", ""))
                quantity = int(raw.get("quantity", 0))
                if quantity < 1 or quantity > 20:
                    raise SimError("Each item quantity must be between 1 and 20")
                selection = CartSelection(
                    item_id,
                    quantity,
                    tuple(str(value) for value in raw.get("variantIds", [])),
                    tuple(str(value) for value in raw.get("addonIds", [])),
                )
                self._selection_total(restaurant_id, selection)
                key = "|".join((item_id, *selection.variant_ids, *selection.addon_ids))
                selections[key] = selection
            version = (state.cart.version + 1) if state.cart else 1
            state.cart = Cart(
                id=state.cart.id if state.cart else f"cart_{uuid.uuid4().hex[:12]}",
                restaurant_id=restaurant_id,
                restaurant_name=restaurant.name,
                address_id=address_id,
                items=selections,
                coupon_code=(
                    state.cart.coupon_code
                    if state.cart and state.cart.restaurant_id == restaurant_id
                    else None
                ),
                version=version,
            )
            return self._cart_data(state)

    def get_food_cart(self, user_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        state = self._user(user_id)
        if arguments.get("addressId"):
            self._address(state, str(arguments["addressId"]))
        return self._cart_data(state)

    def flush_food_cart(self, user_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._user(user_id)
            state.cart = None
            return {"flushed": True}

    def apply_food_coupon(self, user_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._user(user_id)
            if state.cart is None:
                raise SimError("The cart is empty", "CART_EMPTY")
            code = str(arguments.get("couponCode", "")).upper()
            if code not in {"SIM50", "VEG20"}:
                raise SimError(f"Unknown coupon: {code}", "INVALID_COUPON")
            state.cart.coupon_code = code
            state.cart.version += 1
            return self._cart_data(state)

    def place_food_order(self, user_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._user(user_id)
            payment = str(arguments.get("paymentMethod", "Cash")).casefold()
            if payment not in {"cash", "cod", "cash on delivery"}:
                raise SimError("This simulator supports Cash on Delivery only", "PAYMENT_DISABLED")
            if state.cart is None or not state.cart.items:
                raise SimError("The cart is empty", "CART_EMPTY")
            cart_data = self._cart_data(state)
            lines = tuple(dict(value) for value in cart_data["items"])
            order_id = f"SIM-{uuid.uuid4().hex[:8].upper()}"
            order = Order(
                order_id,
                state.cart.restaurant_id,
                state.cart.restaurant_name,
                state.cart.address_id,
                lines,
                round(float(cart_data["pricing"]["to_pay"]) * 100),
                "PLACED",
                now_utc(),
                str(arguments.get("note", "")),
            )
            state.orders[order_id] = order
            state.cart = None
            return {
                "orderId": order_id,
                "status": order.status,
                "orderStatus": order.status,
                "paymentMethod": "Cash",
            }

    @staticmethod
    def _order_data(order: Order) -> dict[str, Any]:
        return {
            "orderId": order.id,
            "restaurantId": order.restaurant_id,
            "restaurantName": order.restaurant_name,
            "addressId": order.address_id,
            "orderTotal": f"{_money(order.total_paise):.2f}",
            "orderStatus": order.status,
            "orderType": "Food",
            "orderedItems": ", ".join(
                f"{line['quantity']} x {line['name']}" for line in order.lines
            ),
            "items": list(order.lines),
            "orderedTime": order.created_at.isoformat(),
            "isActiveOrder": order.status not in {"DELIVERED", "CANCELLED"},
            "paymentMethod": "Cash",
        }

    def _order(self, state: UserState, order_id: str) -> Order:
        order = state.orders.get(order_id)
        if order is None:
            raise SimError(f"Unknown orderId: {order_id}", "ORDER_NOT_FOUND")
        return order

    def get_food_orders(self, user_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        state = self._user(user_id)
        orders = list(state.orders.values())
        if arguments.get("activeOnly"):
            orders = [value for value in orders if value.status not in {"DELIVERED", "CANCELLED"}]
        count = max(1, min(int(arguments.get("orderCount", 10)), 50))
        return {"orders": [self._order_data(value) for value in reversed(orders[-count:])]}

    def get_food_order_details(self, user_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        state = self._user(user_id)
        return {"order": self._order_data(self._order(state, str(arguments.get("orderId", ""))))}

    def get_food_delivery_status(self, user_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        state = self._user(user_id)
        order = self._order(state, str(arguments.get("orderId", "")))
        return {"orderId": order.id, "orderStatus": order.status, "etaMinutes": 25}

    def track_food_order(self, user_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        state = self._user(user_id)
        order = self._order(state, str(arguments.get("orderId", "")))
        progress = {
            "PLACED": 20,
            "CONFIRMED": 35,
            "PREPARING": 55,
            "PICKED_UP": 80,
            "DELIVERED": 100,
        }.get(order.status, 0)
        return {
            "orders": [
                {
                    "orderId": order.id,
                    "title": f"Simulated order: {order.status.replace('_', ' ').title()}",
                    "subtitle": "No real restaurant, rider, payment, or delivery is involved",
                    "etaText": "20-25 simulated minutes"
                    if order.status != "DELIVERED"
                    else "Delivered in simulation",
                    "orderStatus": order.status,
                    "progressPercentage": str(progress),
                    "pollingDuration": "10",
                }
            ]
        }

    def report_error(self, user_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._user(user_id)
            ticket = {
                "ticketId": f"TKT-{uuid.uuid4().hex[:8].upper()}",
                "details": str(arguments.get("details", "")),
                "createdAt": now_utc().isoformat(),
            }
            state.error_reports.append(ticket)
            return ticket

    def advance_order(
        self, user_id: str, order_id: str, status: str | None = None
    ) -> dict[str, Any]:
        with self._lock:
            state = self._user(user_id)
            order = self._order(state, order_id)
            if status is None:
                index = self.ORDER_STATUSES.index(order.status)
                status = self.ORDER_STATUSES[min(index + 1, len(self.ORDER_STATUSES) - 1)]
            status = status.upper()
            if status not in (*self.ORDER_STATUSES, "CANCELLED"):
                raise SimError(f"Unsupported status: {status}")
            state.orders[order_id] = replace(order, status=status)
            return self._order_data(state.orders[order_id])

    def snapshot(self, user_id: str) -> dict[str, Any]:
        state = self._user(user_id)
        return {
            "simulation": True,
            "userId": user_id,
            "addresses": [self._address_data(value) for value in state.addresses.values()],
            "cart": self._cart_data(state),
            "orders": [self._order_data(value) for value in state.orders.values()],
            "errorReports": list(state.error_reports),
            "catalog": {
                "restaurants": len(self.catalog),
                "items": sum(len(value.menu) for value in self.catalog.values()),
            },
        }

    def call(self, user_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "create_address": self.create_address,
            "delete_address": self.delete_address,
            "get_addresses": self.get_addresses,
            "get_restaurant_menu": self.get_restaurant_menu,
            "search_menu": self.search_menu,
            "search_restaurants": self.search_restaurants,
            "apply_food_coupon": self.apply_food_coupon,
            "fetch_food_coupons": self.fetch_food_coupons,
            "flush_food_cart": self.flush_food_cart,
            "get_food_cart": self.get_food_cart,
            "update_food_cart": self.update_food_cart,
            "place_food_order": self.place_food_order,
            "get_food_delivery_status": self.get_food_delivery_status,
            "get_food_order_details": self.get_food_order_details,
            "get_food_orders": self.get_food_orders,
            "track_food_order": self.track_food_order,
            "report_error": self.report_error,
        }
        handler = handlers.get(name)
        if handler is None:
            if name in {"check_payment_status", "confirm_order", "get_payment_options"}:
                raise SimError("Payment tools are intentionally not available", "PAYMENT_DISABLED")
            raise SimError(f"Unknown tool: {name}", "TOOL_NOT_FOUND")
        return handler(user_id, arguments)
