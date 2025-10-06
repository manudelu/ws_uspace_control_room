#!/bin/bash

# --- Build ---
echo "[INFO] Building workspace..."
colcon build

# --- Source workspace ---
echo "[INFO] Sourcing workspace..."
source install/setup.bash

# --- Function to kill all background processes on Ctrl+C ---
cleanup() {
    echo "[INFO] Ctrl+C detected. Killing all processes..."
    kill $BRIDGE_PID $PX4_PID $FLEET_PID 2>/dev/null
    exit 0
}
trap cleanup SIGINT

# --- Start MQTT -> WebSocket bridge ---
echo "[INFO] Starting MQTT -> WebSocket bridge..."
python3 src/mqtt_bridge/mqtt_bridge/websocket.py &
BRIDGE_PID=$!

sleep 2

# --- Launch PX4 instances ---
echo "[INFO] Launching PX4 instances..."
ros2 launch drone_control px4_instances_launch.py &
PX4_PID=$!

sleep 5

# --- Launch Fleet management ---
echo "[INFO] Launching Fleet management..."
ros2 launch drone_control fleet_management_launch.py &
FLEET_PID=$!

# --- Wait for all processes ---
echo "[INFO] All processes started. Waiting..."
wait $BRIDGE_PID $PX4_PID $FLEET_PID