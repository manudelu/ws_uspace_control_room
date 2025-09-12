#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
import json 
import math
import paho.mqtt.client as mqtt # python3 -m pip install paho-mqtt
from std_msgs.msg import String
from drone_interfaces.msg import DroneTelemetry, DroneCommand, Waypoint, DroneStatus
from typing import Dict, Any
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
import os
from dotenv import load_dotenv # pip install python-dotenv

class DroneTelemetryListener(Node):
    def __init__(self):
        super().__init__('drone_telemetry_listener')

        # Load environment variables from .env file
        load_dotenv()

        # Get credentials from environment
        self.mqtt_broker = os.getenv('MQTT_BROKER', 'localhost')  
        self.mqtt_port = int(os.getenv('MQTT_PORT', 1883))  
        self.username = os.getenv('MQTT_USERNAME', '')  
        self.password = os.getenv('MQTT_PASSWORD', '') 

        # QoS profiles
        self.qos_rel = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)
        self.qos_transient = QoSProfile(depth=10,
                                        reliability=ReliabilityPolicy.RELIABLE,
                                        durability=DurabilityPolicy.TRANSIENT_LOCAL)

        # Publishers
        self.drone_pub = self.create_publisher(String, '/drone_id', self.qos_rel)
        self.telemetry_pubs: Dict[str, Any] = {}
        self.action_pubs: Dict[str, Any] = {}
        self.mission_pubs: Dict[str, Any] = {}
        self.ack_pubs: Dict[str, Any] = {}
        self.err_pubs: Dict[str, Any] = {}

        # Setup MQTT
        self.client = mqtt.Client()
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=120)

    def start(self):
        try:
            self.client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.client.loop_start()
            self.get_logger().info("MQTT client started successfully.")
        except Exception as e:
            self.get_logger().error(f"Failed to connect to MQTT broker: {e}")

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.get_logger().info("Connected to MQTT Broker.")
            client.subscribe("fleet/+/telemetry", qos=2)
            client.subscribe("fleet/+/actions", qos=2)
            client.subscribe("fleet/+/missions", qos=2)
            client.subscribe("fleet/+/error", qos=2)
            client.subscribe("fleet/+/ack", qos=2)
        else:
            self.get_logger().error(f"MQTT connect failed: rc={rc}")

    def on_message(self, client, userdata, msg):
        try:
            topic_parts = msg.topic.split('/')
            drone_id_str = topic_parts[1]
            drone_id = ''.join(filter(str.isdigit, drone_id_str))
            self.drone_pub.publish(String(data=drone_id))

            topic_type = topic_parts[2]
            payload = msg.payload.decode("utf-8")

            if topic_type == "telemetry":
                self.process_telemetry(drone_id, payload)
            elif topic_type == "actions":
                self.process_action(drone_id, payload)
            elif topic_type == "missions":
                self.process_mission(drone_id, payload)
            elif topic_type == "ack":
                self.process_ack(drone_id, payload)
            elif topic_type == "error":
                self.process_err(drone_id, payload)
        except Exception as e:
            self.get_logger().error(f"Error processing message: {e}")

    def process_telemetry(self, drone_id: str, payload: str):
        try:
            telemetry_data = json.loads(payload)
            self.publish_telemetry_data(drone_id, telemetry_data)
        except json.JSONDecodeError as e:
            self.get_logger().error(f"Failed to decode telemetry JSON: {e}")

    def process_action(self, drone_id: str, payload: str):
        try:
            action_data = json.loads(payload)
            self.publish_action_data(drone_id, action_data)
        except json.JSONDecodeError as e:
            self.get_logger().error(f"Failed to decode action JSON: {e}")

    def process_mission(self, drone_id: str, payload: str):
        try:
            mission_data = json.loads(payload)
            self.publish_mission_data(drone_id, mission_data)
        except json.JSONDecodeError as e:
            self.get_logger().error(f"Failed to decode mission JSON: {e}")

    def process_ack(self, drone_id: str, payload: str):
        try:
            ack_data = json.loads(payload)
            self.publish_ack_data(drone_id, ack_data)
        except json.JSONDecodeError as e:
            self.get_logger().error(f"Failed to decode ack JSON: {e}")

    def process_err(self, drone_id: str, payload: str):
        try:
            error_data = json.loads(payload)
            self.publish_err_data(drone_id, error_data)
        except json.JSONDecodeError as e:
            self.get_logger().error(f"Failed to decode error JSON: {e}")
    
    def extract_data(self, data: Dict, key_path: list, default_value: Any) -> Any:
        try:
            for key in key_path:
                data = data.get(key, default_value)
            return data
        except (AttributeError, KeyError):
            return default_value

    def publish_telemetry_data(self, drone_id: str, data: Dict):
        if drone_id not in self.telemetry_pubs:
            self.telemetry_pubs[drone_id] = self.create_publisher(DroneTelemetry, f'fleet/drone{drone_id}/telemetry', self.qos_transient)

        telemetry_msg = DroneTelemetry()
        telemetry_msg.drone_id = int(self.extract_data(data, ['drone', 'id'], 0))
        telemetry_msg.type = str(self.extract_data(data, ['drone', 'type'], ""))
        telemetry_msg.error_status = int(self.extract_data(data, ['status', 'error'], 0))
        telemetry_msg.flight_status = int(self.extract_data(data, ['status', 'flight'], 0)) # 0 = STOPED = 0, ON_GROUND = 1, IN_AIR = 2
        telemetry_msg.gear = int(self.extract_data(data, ['status', 'gear'], 0))
        telemetry_msg.mode = int(self.extract_data(data, ['status', 'mode'], 0))

        telemetry_msg.global_position.x = float(self.extract_data(data, ['position', 'latitude'], 0.0))
        telemetry_msg.global_position.y = float(self.extract_data(data, ['position', 'longitude'], 0.0))
        telemetry_msg.global_position.z = float(self.extract_data(data, ['position', 'height'], 0.0))

        telemetry_msg.rc_data.angular.x = float(self.extract_data(data, ['rc', 'roll'], 0.0))
        telemetry_msg.rc_data.angular.y = float(self.extract_data(data, ['rc', 'pitch'], 0.0))
        telemetry_msg.rc_data.angular.z = float(self.extract_data(data, ['rc', 'yaw'], 0.0))
        telemetry_msg.rc_data.linear.x = float(self.extract_data(data, ['rc', 'throttle'], 0.0))

        telemetry_msg.velocity.linear.x = float(self.extract_data(data, ['velocity', 'x'], 0.0))
        telemetry_msg.velocity.linear.y = float(self.extract_data(data, ['velocity', 'y'], 0.0))
        telemetry_msg.velocity.linear.z = float(self.extract_data(data, ['velocity', 'z'], 0.0))
        telemetry_msg.velocity.angular.x = float(self.extract_data(data, ['angularVelocity', 'x'], 0.0))
        telemetry_msg.velocity.angular.y = float(self.extract_data(data, ['angularVelocity', 'y'], 0.0))
        telemetry_msg.velocity.angular.z = float(self.extract_data(data, ['angularVelocity', 'z'], 0.0))

        telemetry_msg.orientation.w = float(self.extract_data(data, ['quaternion', 'q0'], 1.0))
        telemetry_msg.orientation.x = float(self.extract_data(data, ['quaternion', 'q1'], 0.0))
        telemetry_msg.orientation.y = float(self.extract_data(data, ['quaternion', 'q2'], 0.0))
        telemetry_msg.orientation.z = float(self.extract_data(data, ['quaternion', 'q3'], 0.0))

        # Yaw from quaternion (in degrees)
        q0 = telemetry_msg.orientation.w
        q1 = telemetry_msg.orientation.x
        q2 = telemetry_msg.orientation.y
        q3 = telemetry_msg.orientation.z
        telemetry_msg.yaw = math.atan2(
            2 * (q0 * q3 + q1 * q2),
            1 - 2 * (q2 * q2 + q3 * q3)
        ) * (180.0 / math.pi)

        telemetry_msg.avoid_down = float(self.extract_data(data, ['avoidData', 'down'], 0))
        telemetry_msg.avoid_back = float(self.extract_data(data, ['avoidData', 'back'], 0))
        telemetry_msg.avoid_right = float(self.extract_data(data, ['avoidData', 'right'], 0))
        telemetry_msg.avoid_left = float(self.extract_data(data, ['avoidData', 'left'], 0))
        telemetry_msg.avoid_front = float(self.extract_data(data, ['avoidData', 'front'], 0))
        telemetry_msg.avoid_up = float(self.extract_data(data, ['avoidData', 'up'], 0))

        telemetry_msg.battery_capacity = float(self.extract_data(data, ['battery', 'capacity'], 0.0))
        telemetry_msg.battery_voltage = float(self.extract_data(data, ['battery', 'voltage'], 0.0))
        telemetry_msg.battery_current = float(self.extract_data(data, ['battery', 'current'], 0.0))
        telemetry_msg.battery_percentage = float(self.extract_data(data, ['battery', 'percentage'], 0.0))

        telemetry_msg.timestamp = float(self.extract_data(data, ['timestamp'], 0.0))

        self.telemetry_pubs[drone_id].publish(telemetry_msg)
        
    def publish_action_data(self, drone_id: str, data: Dict):
        if drone_id not in self.action_pubs:
            self.action_pubs[drone_id] = self.create_publisher(DroneCommand, f'fleet/drone{drone_id}/actions', self.qos_rel)

        action_msg = DroneCommand()
        action_msg.gcs_id = int(self.extract_data(data, ['gcs_id'], 0))
        action_msg.drone_id = int(self.extract_data(data, ['drone_id'], 0))
        action_msg.action = self.extract_data(data, ['action'], 'N/A')

        if action_msg.action == "Takeoff":
            action_msg.takeoff_height = float(self.extract_data(data, ['parameter', 'takeoff_height'], 0.0))
        elif action_msg.action == "Land":
            pass
        elif action_msg.action == "Return_home":
            pass
        elif action_msg.action == "Goto":
            action_msg.latitude = float(self.extract_data(data, ['parameter', 'lat'], 0.0))
            action_msg.longitude = float(self.extract_data(data, ['parameter', 'lon'], 0.0))
            action_msg.height = float(self.extract_data(data, ['parameter', 'alt'], 0.0))
        elif action_msg.action == "Move":
            action_msg.x = float(self.extract_data(data, ['parameter', 'x'], 0.0))
            action_msg.y = float(self.extract_data(data, ['parameter', 'y'], 0.0))
            action_msg.z = float(self.extract_data(data, ['parameter', 'z'], 0.0))
            action_msg.yaw = float(self.extract_data(data, ['parameter', 'yaw'], 0.0))
        elif action_msg.action == "Rotate":
            action_msg.yaw = float(self.extract_data(data, ['parameter', 'yaw'], 0.0))
        elif action_msg.action == "Hover":
            action_msg.hover_time = float(self.extract_data(data, ['parameter', 'time'], 0.0))
        elif action_msg.action == "Stop":
            pass  
        elif action_msg.action == "Emergency":
            action_msg.emergency_type = self.extract_data(data, ['parameter', 'emergency'], "")
        else:
            self.get_logger().warn(f"Unrecognized action: {action_msg.action}")

        self.action_pubs[drone_id].publish(action_msg)

    def publish_mission_data(self, drone_id: str, data: Dict):
        if drone_id not in self.mission_pubs:
            self.mission_pubs[drone_id] = self.create_publisher(DroneCommand, f'fleet/drone{drone_id}/missions', self.qos_rel) 
        
        mission_msg = DroneCommand()
        mission_msg.gcs_id = int(self.extract_data(data, ['gcs_id'], 0))
        mission_msg.drone_id = int(self.extract_data(data, ['drone_id'], 0))
        mission_msg.mission = self.extract_data(data, ['mission_type'], 'N/A')
        
        if mission_msg.mission == "Waypoint":
            waypoints = self.extract_data(data, ['mission'], [])
            if waypoints:
                mission_msg.waypoints = [self.create_waypoint(wp) for wp in waypoints]
            else:
                self.get_logger().warn(f"No waypoints found for drone{drone_id}")
        elif mission_msg.mission == "Hotpoint":
            mission_msg.latitude = float(self.extract_data(data, ['latitude'], 0.0))
            mission_msg.longitude = float(self.extract_data(data, ['longitude'], 0.0))
            mission_msg.height = float(self.extract_data(data, ['altitude'], 0.0))
            mission_msg.radius = float(self.extract_data(data, ['radius'], 0.0))
            mission_msg.angular_speed = float(self.extract_data(data, ['angular_speed'], 0.0))
            mission_msg.number_of_cycles = float(self.extract_data(data, ['number_of_cycles'], 0.0))
        else:
            self.get_logger().warn(f"Unrecognized mission: {mission_msg.mission}")
            return
            
        self.mission_pubs[drone_id].publish(mission_msg)

    def create_waypoint(self, wp: Dict) -> Waypoint:
        waypoint = Waypoint()
        waypoint.waypoint_number = int(self.extract_data(wp, ['Waypoint Number'], 0))
        waypoint.latitude = float(self.extract_data(wp, ['Latitude'], 0.0))
        waypoint.longitude = float(self.extract_data(wp, ['Longitude'], 0.0))
        waypoint.altitude = float(self.extract_data(wp, ['Altitude'], 0.0))
        return waypoint

    def publish_ack_data(self, drone_id: str, data: Dict):
        if drone_id not in self.ack_pubs:
            self.ack_pubs[drone_id] = self.create_publisher(DroneStatus, f'fleet/drone{drone_id}/ack', self.qos_rel)
        
        ack_msg = DroneStatus()
        ack_msg.drone_id = int(self.extract_data(data, ['drone_id'], 0))
        ack_msg.action = self.extract_data(data, ['action'], 'N/A')
        ack_msg.message = self.extract_data(data, ['message'], 'N/A')
        
        self.ack_pubs[drone_id].publish(ack_msg)

    def publish_err_data(self, drone_id: str, data: Dict):
        if drone_id not in self.err_pubs:
            self.err_pubs[drone_id] = self.create_publisher(DroneStatus, f'fleet/drone{drone_id}/err', self.qos_rel)
        
        error_msg = DroneStatus()
        error_msg.drone_id = int(self.extract_data(data, ['drone_id'], 0))
        error_msg.action = self.extract_data(data, ['action'], 'N/A')
        error_msg.message = self.extract_data(data, ['message'], 'N/A')

        self.err_pubs[drone_id].publish(error_msg)

def main(args=None):
    rclpy.init(args=args)
    node = DroneTelemetryListener()
    node.start()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Shutting down gracefully...")
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
