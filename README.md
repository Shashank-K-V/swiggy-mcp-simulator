# MAV Swiggy Food Simulator

A separate, local-only food-delivery environment for MAV. It mirrors the public Swiggy Food MCP journey closely enough to develop and test MAV without a real Swiggy account, restaurant, rider, payment, or delivery.

## What is included

- 12 seeded Bengaluru restaurants and 96 menu items
- saved-address create/list/delete
- restaurant and menu search
- dietary/allergen metadata, stock and restaurant availability
- menu variants and add-ons
- multi-item cart, delivery fee, tax and coupons (`SIM50`, `VEG20`)
- Cash-on-Delivery order placement only
- order history, details, status, tracking and support tickets
- separate per-user state using the `X-Sim-User` header
- MCP-compatible JSON-RPC endpoint plus test-only administration endpoints

Payment tools are intentionally absent. Every response is labelled as a simulation.

## Run

```bash
cd "/Users/shashank/Desktop/MAV-Swiggy-Simulator"
PYTHONPATH=src python3 -m swiggy_simulator.server
```

The endpoint is `http://127.0.0.1:8790/food`. Health is at `/health` and inspectable state is at `/admin/state`.

In a second Terminal window, start the already-configured MAV UI:

```bash
./run-connected-mav.sh
```

Then open `http://localhost:8766`. The UI will identify its marketplace provider as
`swiggy-http-sim`. The launcher expects LM Studio at `http://127.0.0.1:1234/v1`; change its
model variables if LM Studio exposes a different model identifier.

## Test

```bash
PYTHONPATH=src python3 -m pytest
PYTHONPATH=src python3 -m swiggy_simulator.check
```

## Test-only controls

- `POST /admin/reset` with `{}` resets all users.
- `POST /admin/advance` with `{"orderId":"SIM-..."}` moves an order to its next delivery stage.
- An optional `status` can set `PLACED`, `CONFIRMED`, `PREPARING`, `PICKED_UP`, `DELIVERED`, or `CANCELLED`.

This service binds only to the local computer by default. It is not a clone of Swiggy, does not scrape Swiggy, and should never be represented as a production integration.
