import threading

from swiggy_simulator.load_test import Metrics, run_customer
from swiggy_simulator.server import build_server


def test_load_customer_uses_real_http_and_verifies_multiple_orders() -> None:
    server = build_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/food"
    try:
        result = run_customer(endpoint, 1, 2, Metrics())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert result["orders"] == 2
    assert result["items"] > 2
    assert sum(result["statuses"].values()) == 2
