#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import rclpy
from rclpy.node import Node
from drone_interfaces.srv import FetchAllMissions
import paho.mqtt.client as mqtt
import os
from dotenv import load_dotenv

# MAVLink mission command IDs
MAV_CMD_NAV_WAYPOINT = 16
MAV_CMD_NAV_RETURN_TO_LAUNCH = 20
MAV_CMD_NAV_LAND = 21
MAV_CMD_NAV_TAKEOFF = 22
SKIP_CMDS = {MAV_CMD_NAV_RETURN_TO_LAUNCH, MAV_CMD_NAV_LAND, MAV_CMD_NAV_TAKEOFF}

class MissionClient(Node):
    """ROS2 client for fetching and publishing missions via MQTT."""

    def __init__(self):
        super().__init__('missions_client')

        # Load env vars
        load_dotenv()
        self.mqtt_broker = os.getenv('MQTT_BROKER', 'localhost')
        self.mqtt_port = int(os.getenv('MQTT_PORT', 1883))
        self.username = os.getenv('MQTT_USERNAME', '')
        self.password = os.getenv('MQTT_PASSWORD', '')

        # ROS2 service client
        self.cli = self.create_client(FetchAllMissions, '/fetch_missions')
        while not self.cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().info("Waiting for /fetch_missions service...")

        # Store missions per drone
        self.missions = {}

        # MQTT client
        self.client = mqtt.Client()
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)
        self.client.connect(self.mqtt_broker, self.mqtt_port, 60)
        self.client.loop_start()

    def send_request(self, drone_ids=None):
        """Async call to fetch missions for given drone IDs (or all)."""
        req = FetchAllMissions.Request()
        req.drone_ids = drone_ids if drone_ids else []
        return self.cli.call_async(req)

    def publish_mission(self, drone_id, waypoints):
        """Publish filtered waypoints via MQTT."""
        mission_msg = {
            "mission_type": "Waypoint",
            "gcs_id": 359,
            "drone_id": int(drone_id),
            "mission": [],
        }

        wp_count = 0
        for wp in waypoints:
            cmd = wp.get("command")
            if cmd == MAV_CMD_NAV_WAYPOINT:
                wp_count += 1
                mission_msg["mission"].append({
                    "Waypoint Number": wp_count,
                    "Latitude": wp["x"],
                    "Longitude": wp["y"],
                    "Altitude": wp["z"]
                })
            else:
                self.get_logger().info(
                    f"Drone {drone_id}: Skipping command {cmd} at seq {wp['seq']}"
                )

        if not mission_msg["mission"]:
            self.get_logger().warn(f"No valid waypoints for Drone {drone_id}.")
            return False

        topic = f"fleet/drone{drone_id}/missions"
        self.client.publish(topic, json.dumps(mission_msg))
        self.get_logger().info(
            f"Published {len(mission_msg['mission'])} waypoints for Drone {drone_id} → {topic}"
        )
        return True


class MissionControlGUI:
    """Simple Tkinter GUI to fetch & start missions."""

    def __init__(self, root, node: MissionClient):
        self.root = root
        self.node = node
        self.root.title("Drone Mission Control")
        self.root.geometry("400x350")

        # Main frame
        main_frame = ttk.Frame(root, padding=10)
        main_frame.pack(fill="both", expand=True)

        ttk.Label(main_frame, text="Drone Mission Control",
                  font=("Arial", 14, "bold")).pack(pady=10)

        # Drone list
        self.drone_listbox = tk.Listbox(main_frame, height=8, width=30, selectmode="extended")
        self.drone_listbox.pack(pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Fetch Missions", command=self.fetch_missions).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="Publish Selected", command=self.start_selected_drone).grid(row=0, column=1, padx=5)
        ttk.Button(button_frame, text="Publish All", command=self.start_all_drones).grid(row=1, column=0, columnspan=2, pady=5)

        # Status
        self.status_label = ttk.Label(main_frame, text="Ready", relief="sunken", anchor="w")
        self.status_label.pack(fill="x", pady=5)

    def fetch_missions(self):
        """Fetch missions from ROS2 service in background thread."""
        threading.Thread(target=self._fetch_missions_thread, daemon=True).start()

    def _fetch_missions_thread(self):
        self.status_label.config(text="Fetching missions...")
        future = self.node.send_request()

        rclpy.spin_until_future_complete(self.node, future)
        if not future.result():
            self.status_label.config(text="Fetch failed")
            return

        res = future.result()
        self.node.missions.clear()
        self.drone_listbox.delete(0, tk.END)

        try:
            missions = json.loads(res.missions_json)
            for drone_id, data in missions.items():
                if "error" in data:
                    self.status_label.config(text=f"Drone {drone_id} error")
                else:
                    self.node.missions[drone_id] = data
                    self.drone_listbox.insert(tk.END, f"Drone {drone_id}")
        except Exception as e:
            self.status_label.config(text=f"Parse error: {e}")
            return

        self.status_label.config(text="Missions updated")

    def start_selected_drone(self):
        """Publish mission for selected drones."""
        selected = self.drone_listbox.curselection()
        if not selected:
            messagebox.showwarning("Warning", "No drone selected.")
            return
        for idx in selected:
            drone_id = self.drone_listbox.get(idx).split()[1]
            self._execute_mission(drone_id)

    def start_all_drones(self):
        """Publish missions for all drones."""
        for drone_id in self.node.missions.keys():
            self._execute_mission(drone_id)

    def _execute_mission(self, drone_id):
        """Run publish in background."""
        def task():
            if drone_id not in self.node.missions:
                messagebox.showerror("Error", f"No mission for Drone {drone_id}")
                return
            ok = self.node.publish_mission(drone_id, self.node.missions[drone_id])
            if ok:
                self.status_label.config(text=f"Drone {drone_id}: Mission published")
            else:
                self.status_label.config(text=f"Drone {drone_id}: No waypoints to publish")

        threading.Thread(target=task, daemon=True).start()

def main():
    rclpy.init()
    node = MissionClient()

    root = tk.Tk()
    gui = MissionControlGUI(root, node)

    def on_close():
        node.destroy_node()
        rclpy.shutdown()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
