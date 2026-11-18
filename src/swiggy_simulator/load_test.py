"""Concurrent, repeatable heavy-order test for a running simulator."""

from __future__ import annotations

import argparse
import json
import math
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

AREAS = ("Indiranagar", "Koramangala", "Whitefield", "Jayanagar")
FINAL_STATUSES = (
    "PLACED",
    "CONFIRMED",
    "PREPARING",
    "PICKED_UP",
    "DELIVERED",
    "CANCELLED",
)


@dataclass(slots=True)
class Metrics:
    latencies_ms: list[float] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, elapsed_ms: float) -> None:
        with self.lock:
            self.latencies_ms.append(elapsed_ms)


class Client:
    def __init__(self, endpoint: str, user_id: str, metrics: Metrics) -> None:
        self.endpoint = endpoint
        self.user_id = user_id
        self.metrics = metrics
        self.request_id = 0

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.request_id += 1
        body = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": self.request_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        ).encode()
        request = urllib.request.Request(
            self.endpoint,
            body,
            {"Content-Type": "application/json", "X-Sim-User": self.user_id},
        )
        started = time.perf_counter()
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.load(response)
        self.metrics.add((time.perf_counter() - started) * 1_000)
        result = payload.get("result", {})
        if result.get("isError"):
            error = result.get("structuredContent", {}).get("error", {})
            raise RuntimeError(f"{name}: {error.get('code')} - {error.get('message')}")
        data = result.get("structuredContent", {}).get("data")
        if not isinstance(data, dict):
            raise RuntimeError(f"{name}: response did not contain structured data")
        return data

    def advance(self, order_id: str, status: str) -> dict[str, Any]:
        body = json.dumps({"orderId": order_id, "status": status}).encode()
        request = urllib.request.Request(
            urljoin(self.endpoint, "/admin/advance"),
            body,
            {"Content-Type": "application/json", "X-Sim-User": self.user_id},
        )
        started = time.perf_counter()
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.load(response)
        self.metrics.add((time.perf_counter() - started) * 1_000)
        if not isinstance(payload, dict) or payload.get("orderId") != order_id:
            raise RuntimeError("Admin lifecycle update returned an invalid order")
        return payload


def _ensure_addresses(client: Client) -> dict[str, str]:
    saved = client.call("get_addresses", {})["addresses"]
    by_area = {str(address["locality"]): str(address["id"]) for address in saved}
    for number, area in enumerate(AREAS, start=1):
        if area in by_area:
            continue
        created = client.call(
            "create_address",
            {
                "fullAddress": f"{number} Load Test Avenue, {area}, Bengaluru",
                "addressLine": f"{number} Load Test Avenue",
                "addressLine2": "Stress Test Building",
                "locality": area,
                "city": "Bengaluru",
                "postalCode": f"5600{40 + number}",
                "addressCategory": "Other",
                "userName": f"Load Customer {client.user_id}",
                "userPhone": f"91{number:08d}",
            },
        )["address"]
        by_area[area] = str(created["id"])
    return by_area


def _cart_items(menu: dict[str, Any], order_number: int) -> list[dict[str, Any]]:
    available = [
        item for category in menu["categories"] for item in category["items"] if item["inStock"]
    ]
    line_count = min(len(available), 3 + order_number % 4)
    rotated = (
        available[order_number % len(available) :] + available[: order_number % len(available)]
    )
    cart_items = []
    for line_number, item in enumerate(rotated[:line_count]):
        selection: dict[str, Any] = {
            "menu_item_id": item["id"],
            "quantity": 1 + (order_number + line_number) % 4,
        }
        if item["variants"]:
            selection["variantIds"] = [item["variants"][-1]["id"]]
        if item["addons"]:
            selection["addonIds"] = [addon["id"] for addon in item["addons"][: 1 + line_number % 2]]
        cart_items.append(selection)
    return cart_items


def run_customer(
    endpoint: str,
    customer_number: int,
    orders_per_customer: int,
    metrics: Metrics,
) -> dict[str, Any]:
    user_id = f"heavy-customer-{customer_number:03d}"
    client = Client(endpoint, user_id, metrics)
    addresses = _ensure_addresses(client)
    created_orders: list[str] = []
    total_items = 0
    total_value = 0.0
    restaurants_used: set[str] = set()
    statuses: dict[str, int] = {status: 0 for status in FINAL_STATUSES}

    for order_number in range(orders_per_customer):
        area = AREAS[(customer_number + order_number) % len(AREAS)]
        address_id = addresses[area]
        discovered = client.call("search_restaurants", {"addressId": address_id, "query": ""})[
            "restaurants"
        ]
        open_restaurants = [
            restaurant for restaurant in discovered if restaurant["availabilityStatus"] == "OPEN"
        ]
        if not open_restaurants:
            raise RuntimeError(f"No open restaurants for {area}")
        restaurant = open_restaurants[(customer_number + order_number) % len(open_restaurants)]
        restaurants_used.add(str(restaurant["id"]))
        menu = client.call(
            "get_restaurant_menu",
            {"addressId": address_id, "restaurantId": restaurant["id"]},
        )
        desired = _cart_items(menu, customer_number + order_number)
        cart = client.call(
            "update_food_cart",
            {
                "addressId": address_id,
                "restaurantId": restaurant["id"],
                "restaurantName": restaurant["name"],
                "cartItems": desired,
            },
        )
        if len(cart["items"]) != len(desired):
            raise RuntimeError("The saved cart line count differs from the requested cart")
        coupon = "SIM50" if order_number % 2 == 0 else "VEG20"
        cart = client.call("apply_food_coupon", {"couponCode": coupon})
        fresh = client.call("get_food_cart", {"addressId": address_id})
        if fresh["version"] != cart["version"] or fresh["pricing"] != cart["pricing"]:
            raise RuntimeError("Fresh cart verification did not match the coupon cart")
        expected_total = float(fresh["pricing"]["to_pay"])
        if expected_total <= 0:
            raise RuntimeError("Heavy cart total must be positive")
        placed = client.call(
            "place_food_order",
            {
                "addressId": address_id,
                "paymentMethod": "Cash",
                "note": f"Heavy simulation order {order_number + 1}",
            },
        )
        order_id = str(placed["orderId"])
        details = client.call("get_food_order_details", {"orderId": order_id})["order"]
        tracked = client.call("track_food_order", {"orderId": order_id})["orders"][0]
        status = client.call("get_food_delivery_status", {"orderId": order_id})
        if float(details["orderTotal"]) != expected_total:
            raise RuntimeError("Placed order total differs from the verified cart total")
        if tracked["orderStatus"] != "PLACED" or status["orderStatus"] != "PLACED":
            raise RuntimeError("New order did not enter the PLACED state")
        final_status = FINAL_STATUSES[(customer_number + order_number) % len(FINAL_STATUSES)]
        if final_status != "PLACED":
            client.advance(order_id, final_status)
            final_tracking = client.call("track_food_order", {"orderId": order_id})["orders"][0]
            if final_tracking["orderStatus"] != final_status:
                raise RuntimeError("Lifecycle update was not reflected in tracking")
        statuses[final_status] += 1
        created_orders.append(order_id)
        total_items += sum(int(item["quantity"]) for item in fresh["items"])
        total_value += expected_total

    history = client.call(
        "get_food_orders", {"activeOnly": False, "orderCount": orders_per_customer}
    )["orders"]
    history_ids = {str(order["orderId"]) for order in history}
    if not set(created_orders).issubset(history_ids):
        raise RuntimeError("One or more placed orders are missing from order history")
    return {
        "customer": user_id,
        "orders": len(created_orders),
        "items": total_items,
        "value": round(total_value, 2),
        "restaurants": len(restaurants_used),
        "statuses": statuses,
    }


def _percentile(values: list[float], percentage: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * percentage) - 1))
    return round(ordered[index], 2)


def reset(endpoint: str) -> None:
    admin_url = urljoin(endpoint, "/admin/reset")
    request = urllib.request.Request(admin_url, b"{}", {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError("Could not reset simulator state")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create and verify many heavy simulated orders")
    parser.add_argument("--url", default="http://127.0.0.1:8790/food")
    parser.add_argument("--customers", type=int, default=20)
    parser.add_argument("--orders-per-customer", type=int, default=5)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.customers <= 200:
        parser.error("--customers must be between 1 and 200")
    if not 1 <= args.orders_per_customer <= 20:
        parser.error("--orders-per-customer must be between 1 and 20")
    if not 1 <= args.workers <= 50:
        parser.error("--workers must be between 1 and 50")
    if args.reset:
        reset(args.url)

    metrics = Metrics()
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=min(args.workers, args.customers)) as pool:
        futures = {
            pool.submit(
                run_customer,
                args.url,
                customer_number,
                args.orders_per_customer,
                metrics,
            ): customer_number
            for customer_number in range(1, args.customers + 1)
        }
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:  # noqa: BLE001 - load report must retain every failure
                failures.append(
                    {"customer": f"heavy-customer-{futures[future]:03d}", "error": str(exc)}
                )

    elapsed = time.perf_counter() - started
    status_totals = {
        status: sum(int(result["statuses"][status]) for result in results)
        for status in FINAL_STATUSES
    }
    summary = {
        "ok": not failures,
        "simulationOnly": True,
        "payment": "Cash simulation only",
        "customers": args.customers,
        "ordersRequested": args.customers * args.orders_per_customer,
        "ordersVerified": sum(int(result["orders"]) for result in results),
        "itemUnitsVerified": sum(int(result["items"]) for result in results),
        "simulatedOrderValue": round(sum(float(result["value"]) for result in results), 2),
        "finalOrderStatuses": status_totals,
        "httpRequests": len(metrics.latencies_ms),
        "elapsedSeconds": round(elapsed, 2),
        "ordersPerSecond": round(sum(int(result["orders"]) for result in results) / elapsed, 2),
        "latencyMs": {
            "median": _percentile(metrics.latencies_ms, 0.5),
            "p95": _percentile(metrics.latencies_ms, 0.95),
            "maximum": round(max(metrics.latencies_ms, default=0.0), 2),
        },
        "failures": failures,
    }
    print(json.dumps(summary, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
