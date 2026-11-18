"""Minimal JSON-RPC MCP endpoint for the simulator."""

from __future__ import annotations

from typing import Any

from swiggy_simulator.service import SimError, SwiggyFoodService


def _schema(
    required: tuple[str, ...] = (), properties: dict[str, Any] | None = None
) -> dict[str, Any]:
    value: dict[str, Any] = {"type": "object", "properties": properties or {}}
    if required:
        value["required"] = list(required)
    return value


COMMON_ADDRESS = {"addressId": {"type": "string"}}
TOOLS: dict[str, dict[str, Any]] = {
    "create_address": _schema(
        ("fullAddress", "addressLine", "city", "postalCode", "userName", "userPhone"),
        {
            "fullAddress": {"type": "string"},
            "addressLine": {"type": "string"},
            "addressLine2": {"type": "string"},
            "locality": {"type": "string"},
            "city": {"type": "string"},
            "postalCode": {"type": "string"},
            "addressCategory": {"type": "string"},
            "userName": {"type": "string"},
            "userPhone": {"type": "string"},
        },
    ),
    "delete_address": _schema(("addressId",), COMMON_ADDRESS),
    "get_addresses": _schema(),
    "search_restaurants": _schema(("addressId",), {**COMMON_ADDRESS, "query": {"type": "string"}}),
    "get_restaurant_menu": _schema(
        ("addressId", "restaurantId"), {**COMMON_ADDRESS, "restaurantId": {"type": "string"}}
    ),
    "search_menu": _schema(
        ("addressId", "query"),
        {**COMMON_ADDRESS, "query": {"type": "string"}, "restaurantId": {"type": "string"}},
    ),
    "fetch_food_coupons": _schema(),
    "apply_food_coupon": _schema(("couponCode",), {"couponCode": {"type": "string"}}),
    "flush_food_cart": _schema((), COMMON_ADDRESS),
    "get_food_cart": _schema((), COMMON_ADDRESS),
    "update_food_cart": _schema(
        ("addressId", "restaurantId", "cartItems"),
        {
            **COMMON_ADDRESS,
            "restaurantId": {"type": "string"},
            "restaurantName": {"type": "string"},
            "cartItems": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["menu_item_id", "quantity"],
                    "properties": {
                        "menu_item_id": {"type": "string"},
                        "quantity": {"type": "integer"},
                        "variantIds": {"type": "array", "items": {"type": "string"}},
                        "addonIds": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
        },
    ),
    "place_food_order": _schema(
        (),
        {
            **COMMON_ADDRESS,
            "paymentMethod": {"type": "string", "enum": ["Cash"]},
            "note": {"type": "string"},
        },
    ),
    "get_food_delivery_status": _schema(("orderId",), {"orderId": {"type": "string"}}),
    "get_food_order_details": _schema(("orderId",), {"orderId": {"type": "string"}}),
    "get_food_orders": _schema(
        (), {"activeOnly": {"type": "boolean"}, "orderCount": {"type": "integer"}}
    ),
    "track_food_order": _schema(("orderId",), {"orderId": {"type": "string"}}),
    "report_error": _schema(
        ("details",), {"details": {"type": "string"}, "orderId": {"type": "string"}}
    ),
}

DESCRIPTIONS = {
    "create_address": "Create a simulated delivery address.",
    "delete_address": "Delete a simulated saved address.",
    "get_addresses": "List saved simulated delivery addresses.",
    "search_restaurants": "Search available simulated restaurants for an address.",
    "get_restaurant_menu": "Get a simulated restaurant menu with safety metadata.",
    "search_menu": "Search simulated menu items.",
    "fetch_food_coupons": "List deterministic simulator coupons.",
    "apply_food_coupon": "Apply a simulator coupon to the active cart.",
    "flush_food_cart": "Clear the active simulated cart.",
    "get_food_cart": "Read the active cart and complete price breakdown.",
    "update_food_cart": "Replace the active cart contents, including variants and add-ons.",
    "place_food_order": "Place a simulated Cash-on-Delivery order. No payment occurs.",
    "get_food_delivery_status": "Read a simulated delivery status.",
    "get_food_order_details": "Read full simulated order details.",
    "get_food_orders": "List simulated order history.",
    "track_food_order": "Track a simulated order. Poll no faster than every 10 seconds.",
    "report_error": "Create a simulated support ticket.",
}


def tool_list() -> list[dict[str, Any]]:
    return [
        {"name": name, "description": DESCRIPTIONS[name], "inputSchema": schema}
        for name, schema in TOOLS.items()
    ]


def _tool_result(data: dict[str, Any], message: str = "Simulated Swiggy result") -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": message}],
        "structuredContent": {"success": True, "data": data, "message": message},
        "isError": False,
    }


def _tool_error(error: SimError) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": str(error)}],
        "structuredContent": {
            "success": False,
            "error": {"code": error.code, "message": str(error)},
        },
        "isError": True,
    }


def dispatch(
    service: SwiggyFoodService, user_id: str, request: dict[str, Any]
) -> dict[str, Any] | None:
    request_id = request.get("id")
    if request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32600, "message": "Invalid Request"},
        }
    method = request["method"]
    params = request.get("params", {})
    try:
        if method == "initialize":
            result: dict[str, Any] = {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "mav-swiggy-simulator", "version": "1.0.0"},
                "instructions": (
                    "Local simulation only. Cash on Delivery is simulated; payments are disabled."
                ),
            }
        elif method == "notifications/initialized":
            return None
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": tool_list()}
        elif method == "tools/call":
            if not isinstance(params, dict) or not isinstance(params.get("arguments", {}), dict):
                raise SimError("tools/call arguments must be an object")
            try:
                data = service.call(
                    user_id, str(params.get("name", "")), params.get("arguments", {})
                )
                result = _tool_result(data)
            except SimError as exc:
                result = _tool_error(exc)
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": "Method not found"},
            }
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except SimError as exc:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32602, "message": str(exc), "data": {"code": exc.code}},
        }
