#!/bin/sh
set -eu

SCRIPT_DIRECTORY=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
MAV_PROJECT=${MAV_PROJECT:-"$SCRIPT_DIRECTORY/../mav-multi-agent-voice-ordering"}

if [ ! -d "$MAV_PROJECT/src/mav_ordering" ]; then
  echo "MAV was not found at: $MAV_PROJECT" >&2
  echo "Set MAV_PROJECT to your MAV checkout before running this script." >&2
  exit 1
fi
export MAV_MARKETPLACE_PROVIDER="swiggy-http-sim"
export MAV_SWIGGY_SIM_URL="http://127.0.0.1:8790/food"
export MAV_SWIGGY_SIM_USER="mav-ui-user"
export MAV_MODEL_PROVIDER="lmstudio"
export MAV_MODEL_NAME="qwen2.5"
export MAV_MODEL_BASE_URL="http://127.0.0.1:1234/v1"
export PYTHONPATH="$MAV_PROJECT/src"

cd "$MAV_PROJECT"
exec python3 -m mav_ordering.web.app --port 8766
