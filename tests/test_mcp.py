from swiggy_simulator.mcp import TOOLS, dispatch
from swiggy_simulator.service import SwiggyFoodService


def test_tools_list_has_all_non_payment_tools_only() -> None:
    response = dispatch(
        SwiggyFoodService(), "u", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    )
    names = {tool["name"] for tool in response["result"]["tools"]}
    assert len(names) == 17
    assert names == set(TOOLS)
    assert names.isdisjoint({"check_payment_status", "confirm_order", "get_payment_options"})


def test_mcp_structured_content_and_error_envelope() -> None:
    service = SwiggyFoodService()
    ok = dispatch(
        service,
        "u",
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "get_addresses", "arguments": {}},
        },
    )
    assert ok["result"]["structuredContent"]["success"] is True
    error = dispatch(
        service,
        "u",
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "get_payment_options", "arguments": {}},
        },
    )
    assert error["result"]["isError"] is True
    assert error["result"]["structuredContent"]["error"]["code"] == "PAYMENT_DISABLED"
