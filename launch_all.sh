#!/bin/bash
set -e  # Exit immediately if any command fails

# --- Build workspace ---
echo "[INFO] Building workspace..."
colcon build

# --- Source workspace ---
echo "[INFO] Sourcing workspace..."
source install/setup.bash

# --- Function to clean up all process groups ---
cleanup() {
    echo "[INFO] Ctrl+C detected. Killing all process groups..."

    for PID in $BRIDGE_PID $PX4_PID $FLEET_PID; do
        if [[ ! -z "$PID" ]]; then
            echo "[INFO] Killing process group $PID"
            kill -TERM -$PID 2>/dev/null || true
            sleep 1
            kill -9 -$PID 2>/dev/null || true
        fi
    done

    echo "[INFO] Cleanup complete. Exiting."
    exit 0
}

trap cleanup SIGINT SIGTERM

# --- Start MQTT -> WebSocket bridge ---
echo "[INFO] Starting MQTT -> WebSocket bridge..."
setsid python3 src/mqtt_bridge/mqtt_bridge/websocket.py &
BRIDGE_PID=$!
echo "[INFO] MQTT bridge PID: $BRIDGE_PID"

sleep 2  # Allow MQTT bridge to initialize

# --- Launch PX4 SITL instances ---
echo "[INFO] Launching PX4 instances..."
setsid ros2 launch drone_control px4_instances_launch.py &
PX4_PID=$!
echo "[INFO] PX4 launch PID: $PX4_PID"

sleep 8  # Give PX4 and MicroXRCEAgent time to initialize

# --- Launch Fleet management ---
echo "[INFO] Launching Fleet management..."
setsid ros2 launch drone_control fleet_management_launch.py &
FLEET_PID=$!
echo "[INFO] Fleet management PID: $FLEET_PID"

# --- Wait for all process groups ---
echo "[INFO] All processes started. Waiting..."
wait $BRIDGE_PID $PX4_PID $FLEET_PID
