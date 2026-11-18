#!/bin/sh
set -eu

MAV_PROJECT="/Users/shashank/Desktop/MAV-Ordering App"
export MAV_MARKETPLACE_PROVIDER="swiggy-http-sim"
export MAV_SWIGGY_SIM_URL="http://127.0.0.1:8790/food"
export MAV_SWIGGY_SIM_USER="mav-ui-user"
export MAV_MODEL_PROVIDER="lmstudio"
export MAV_MODEL_NAME="qwen2.5"
export MAV_MODEL_BASE_URL="http://127.0.0.1:1234/v1"
export PYTHONPATH="$MAV_PROJECT/src"

cd "$MAV_PROJECT"
exec python3 -m mav_ordering.web.app --port 8766
