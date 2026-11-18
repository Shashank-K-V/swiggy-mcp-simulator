"""End-to-end smoke check against a running simulator."""

from __future__ import annotations

import argparse
import json
import urllib.request


def call(
    endpoint: str, request_id: int, name: str, arguments: dict[str, object]
) -> dict[str, object]:
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    ).encode()
    request = urllib.request.Request(
        endpoint, body, {"Content-Type": "application/json", "X-Sim-User": "smoke-user"}
    )
    with urllib.request.urlopen(request, timeout=3) as response:
        payload = json.load(response)
    result = payload["result"]
    if result.get("isError"):
        raise RuntimeError(result["structuredContent"]["error"]["message"])
    return result["structuredContent"]["data"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8790/food")
    args = parser.parse_args()
    addresses = call(args.url, 1, "get_addresses", {})
    address_id = addresses["resolution"]["defaultAddressId"]
    restaurants = call(
        args.url, 2, "search_restaurants", {"addressId": address_id, "query": "Chinese"}
    )
    restaurant = restaurants["restaurants"][0]
    menu = call(
        args.url,
        3,
        "get_restaurant_menu",
        {"addressId": address_id, "restaurantId": restaurant["id"]},
    )
    item = menu["categories"][0]["items"][0]
    cart = call(
        args.url,
        4,
        "update_food_cart",
        {
            "addressId": address_id,
            "restaurantId": restaurant["id"],
            "restaurantName": restaurant["name"],
            "cartItems": [{"menu_item_id": item["id"], "quantity": 2}],
        },
    )
    order = call(
        args.url, 5, "place_food_order", {"addressId": address_id, "paymentMethod": "Cash"}
    )
    tracked = call(args.url, 6, "track_food_order", {"orderId": order["orderId"]})
    print(
        json.dumps(
            {
                "ok": True,
                "restaurant": restaurant["name"],
                "items": len(cart["items"]),
                "total": cart["pricing"]["to_pay"],
                "orderId": order["orderId"],
                "status": tracked["orders"][0]["orderStatus"],
                "payment": "Cash simulation only",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
