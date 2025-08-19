#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from drone_interfaces.srv import FetchAllMissions
import json
from typing import Dict, List, Any
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import os

# MAVLink mission command IDs (from common.xml)
MAV_CMD_NAV_WAYPOINT = 16
MAV_CMD_NAV_LOITER_UNLIM = 17
MAV_CMD_NAV_LOITER_TURNS = 18
MAV_CMD_NAV_LOITER_TIME = 19
MAV_CMD_NAV_RETURN_TO_LAUNCH = 20
MAV_CMD_NAV_LAND = 21
MAV_CMD_NAV_TAKEOFF = 22

SKIP_CMDS = {MAV_CMD_NAV_RETURN_TO_LAUNCH, MAV_CMD_NAV_LAND, MAV_CMD_NAV_TAKEOFF}

class MissionClient(Node):
    def __init__(self):
        super().__init__('missions_client')

        # Load environment variables from .env file
        load_dotenv()

        # Get credentials from environment
        self.mqtt_broker = os.getenv('MQTT_BROKER', 'localhost')  
        self.mqtt_port = int(os.getenv('MQTT_PORT', 1883))  
        self.username = os.getenv('MQTT_USERNAME', '')  
        self.password = os.getenv('MQTT_PASSWORD', '') 

        # ROS2 service client
        self.cli = self.create_client(FetchAllMissions, '/fetch_missions')
        while not self.cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().info("Service /fetch_missions not available, waiting...")

        # Store missions per drone
        self.missions: Dict[str, List[Dict[str, Any]]] = {}

        self.client = mqtt.Client()
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)
        self.client.connect(self.mqtt_broker, self.mqtt_port, 60)
        self.client.loop_start()

    def send_request(self, drone_ids=None):
        req = FetchAllMissions.Request()
        req.drone_ids = drone_ids if drone_ids is not None else []
        return self.cli.call_async(req)

    def publish_mission(self, drone_id: str, waypoint_group: List[Dict[str, Any]]) -> None:
        """Publish waypoints (skip takeoff, land, RTL) via MQTT."""
        mission_msg = {
            "mission_type": "Waypoint",
            "gcs_id": 359,
            "drone_id": int(drone_id),
            "mission": [],
        }

        wp_count = 0  # numbering starts fresh
        for wp in waypoint_group:
            cmd = wp.get("command")
            if cmd == MAV_CMD_NAV_WAYPOINT:  # Only keep waypoints
                wp_count += 1
                mission_msg["mission"].append({
                    "Waypoint Number": wp_count,
                    "Latitude": wp["x"],
                    "Longitude": wp["y"],
                    "Altitude": wp["z"]
                })

                self.get_logger().info(
                    f"Drone {drone_id}: Waypoint {wp_count} "
                    f"(seq={wp['seq']}, lat={wp['x']:.6f}, lon={wp['y']:.6f}, alt={wp['z']}, cmd={cmd})"
                )
            else:
                self.get_logger().info(
                    f"Drone {drone_id}: Skipping command {cmd} at seq {wp['seq']}"
                )

        if not mission_msg["mission"]:
            self.get_logger().warn(f"No valid waypoints for Drone {drone_id}. Mission not published.")
            return

        topic = f"fleet/drone{drone_id}/missions"
        self.client.publish(topic, json.dumps(mission_msg))
        self.get_logger().info(
            f"Published {len(mission_msg['mission'])} waypoints for Drone {drone_id} to {topic}"
        )

def main(args=None):
    rclpy.init(args=args)
    node = MissionClient()

    # Example 1: fetch missions for all registered drones
    future = node.send_request()

    # Example 2: fetch specific drones (uncomment to test)
    # future = node.send_request([1, 3])

    rclpy.spin_until_future_complete(node, future)
    if future.result() is not None:
        res = future.result()
        if res.success:
            node.get_logger().info("Missions fetched successfully!")
        else:
            node.get_logger().warn("Some missions failed.")

        try:
            missions = json.loads(res.missions_json)
            for drone_id, data in missions.items():
                if "error" in data:
                    node.get_logger().error(f"Drone {drone_id} error: {data['error']}")
                else:
                    node.missions[drone_id] = data
                    node.get_logger().info(f"Stored mission for Drone {drone_id} with {len(data)} items")
                    node.publish_mission(drone_id, data)

        except Exception as e:
            node.get_logger().error(f"Failed to parse missions JSON: {e}")
    else:
        node.get_logger().error("Service call failed.")

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
