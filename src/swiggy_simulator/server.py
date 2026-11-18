"""Loopback-only HTTP server exposing MCP and simulator administration."""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from swiggy_simulator.mcp import dispatch
from swiggy_simulator.service import SimError, SwiggyFoodService

MAX_BODY_BYTES = 1_000_000


class SimulatorServer(ThreadingHTTPServer):
    service: SwiggyFoodService


class Handler(BaseHTTPRequestHandler):
    server: SimulatorServer

    def log_message(self, format: str, *args: object) -> None:
        print(f"[swiggy-sim] {self.address_string()} {format % args}")

    def _user_id(self) -> str:
        return self.headers.get("X-Sim-User", "demo-user")[:100]

    def _send(self, status: int, payload: object) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Swiggy-Simulation", "true")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, object]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise SimError("Invalid Content-Length") from exc
        if length <= 0 or length > MAX_BODY_BYTES:
            raise SimError("Request body size must be between 1 byte and 1 MB")
        try:
            value = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SimError("Request body must be valid JSON") from exc
        if not isinstance(value, dict):
            raise SimError("Request body must be a JSON object")
        return value

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "mav-swiggy-simulator",
                    "simulation": True,
                    "payments": False,
                },
            )
            return
        if parsed.path == "/admin/state":
            user = parse_qs(parsed.query).get("user", [self._user_id()])[0]
            self._send(HTTPStatus.OK, self.server.service.snapshot(user))
            return
        self._send(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:
        try:
            payload = self._read_json()
            if self.path == "/food":
                response = dispatch(self.server.service, self._user_id(), payload)
                if response is None:
                    self.send_response(HTTPStatus.NO_CONTENT)
                    self.end_headers()
                else:
                    self._send(HTTPStatus.OK, response)
                return
            if self.path == "/admin/reset":
                self.server.service.reset()
                self._send(HTTPStatus.OK, {"reset": True})
                return
            if self.path == "/admin/advance":
                result = self.server.service.advance_order(
                    self._user_id(),
                    str(payload.get("orderId", "")),
                    str(payload["status"]) if payload.get("status") else None,
                )
                self._send(HTTPStatus.OK, result)
                return
            self._send(HTTPStatus.NOT_FOUND, {"error": "Not found"})
        except SimError as exc:
            self._send(HTTPStatus.BAD_REQUEST, {"error": {"code": exc.code, "message": str(exc)}})


def build_server(host: str = "127.0.0.1", port: int = 8790) -> SimulatorServer:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("The simulator binds to loopback only")
    server = SimulatorServer((host, port), Handler)
    server.service = SwiggyFoodService()
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local MAV Swiggy Food simulator")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args()
    server = build_server(args.host, args.port)
    print(f"MAV Swiggy simulator listening at http://{args.host}:{args.port}/food")
    print("SIMULATION ONLY · CASH ON DELIVERY ONLY · NO PAYMENT TOOLS")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
