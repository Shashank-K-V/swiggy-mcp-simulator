from swiggy_simulator.service import SimError, SwiggyFoodService


def test_full_multi_item_coupon_cod_order_and_tracking() -> None:
    service = SwiggyFoodService()
    user = "alice"
    addresses = service.call(user, "get_addresses", {})
    address_id = addresses["resolution"]["defaultAddressId"]
    restaurants = service.call(
        user, "search_restaurants", {"addressId": address_id, "query": "Chinese"}
    )
    restaurant = restaurants["restaurants"][0]
    menu = service.call(
        user, "get_restaurant_menu", {"addressId": address_id, "restaurantId": restaurant["id"]}
    )
    items = [item for category in menu["categories"] for item in category["items"]]
    first = items[0]
    second = next(item for item in items if item["variants"] and item["addons"])
    large = second["variants"][1]["id"]
    addon = second["addons"][0]["id"]
    cart = service.call(
        user,
        "update_food_cart",
        {
            "addressId": address_id,
            "restaurantId": restaurant["id"],
            "cartItems": [
                {"menu_item_id": first["id"], "quantity": 1},
                {
                    "menu_item_id": second["id"],
                    "quantity": 2,
                    "variantIds": [large],
                    "addonIds": [addon],
                },
            ],
        },
    )
    assert len(cart["items"]) == 2
    discounted = service.call(user, "apply_food_coupon", {"couponCode": "SIM50"})
    assert discounted["pricing"]["discount"] == 50
    order = service.call(user, "place_food_order", {"paymentMethod": "Cash"})
    assert order["orderStatus"] == "PLACED"
    assert service.call(user, "get_food_cart", {})["items"] == []
    assert (
        service.call(user, "track_food_order", {"orderId": order["orderId"]})["orders"][0][
            "progressPercentage"
        ]
        == "20"
    )
    service.advance_order(user, order["orderId"], "DELIVERED")
    assert (
        service.call(user, "get_food_delivery_status", {"orderId": order["orderId"]})["orderStatus"]
        == "DELIVERED"
    )


def test_users_are_isolated_and_payments_are_blocked() -> None:
    service = SwiggyFoodService()
    service.call(
        "alice",
        "create_address",
        {
            "fullAddress": "1 A",
            "addressLine": "1",
            "city": "Bengaluru",
            "postalCode": "560001",
            "userName": "Alice",
            "userPhone": "9000000001",
        },
    )
    assert len(service.call("alice", "get_addresses", {})["addresses"]) == 3
    assert len(service.call("bob", "get_addresses", {})["addresses"]) == 2
    try:
        service.call("alice", "get_payment_options", {})
    except SimError as exc:
        assert exc.code == "PAYMENT_DISABLED"
    else:
        raise AssertionError("payment tools must be absent")


def test_closed_restaurant_out_of_stock_and_bad_coupon_fail() -> None:
    service = SwiggyFoodService()
    address = service.call("u", "get_addresses", {})["resolution"]["defaultAddressId"]
    closed = service.catalog["rest_012"]
    try:
        service.call(
            "u",
            "update_food_cart",
            {"addressId": address, "restaurantId": closed.id, "cartItems": []},
        )
    except SimError as exc:
        assert exc.code == "RESTAURANT_CLOSED"
    else:
        raise AssertionError("closed restaurant must be rejected")
    unavailable = service.catalog["rest_001"].menu[-1]
    try:
        service.call(
            "u",
            "update_food_cart",
            {
                "addressId": address,
                "restaurantId": "rest_001",
                "cartItems": [{"menu_item_id": unavailable.id, "quantity": 1}],
            },
        )
    except SimError as exc:
        assert exc.code == "ITEM_UNAVAILABLE"
    else:
        raise AssertionError("unavailable item must be rejected")
