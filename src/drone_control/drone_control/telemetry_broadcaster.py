#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from drone_interfaces.msg import DroneTelemetry 
import socket
import json
from typing import Dict, Any

class TelemetryBroadcaster(Node):
    def __init__(self):
        super().__init__("telemetry_broadcaster")
        
        self.declare_parameter("udp_host", "192.168.9.37")
        self.declare_parameter("udp_port_base", 3000)
        
        self.udp_host = self.get_parameter("udp_host").value
        self.udp_port_base = self.get_parameter("udp_port_base").value

        self.subscribers: Dict[str, Any] = {}
        self.telemetry_data: Dict[str, Dict[str, float]] = {}
        self.udp_sockets: Dict[str, socket.socket] = {}

        # Create subscriber for drone registration
        self.drone_id_sub = self.create_subscription(
            String,
            "/drone_id",
            self.drone_id_callback,
            10
        )

        # Create timer for sending UDP data
        self.timer = self.create_timer(0.1, self.send_udp_data)  # 10Hz

        self.get_logger().info("UDP Sender node initialized")

    def drone_id_callback(self, msg: String) -> None:
        drone_id = msg.data
        telemetry_topic = f"fleet/drone{drone_id}/telemetry"

        if drone_id not in self.subscribers:
            self.subscribers[drone_id] = self.create_subscription(
                DroneTelemetry,
                telemetry_topic,
                lambda msg, id=drone_id: self.telemetry_callback(msg, id),
                10
            )
            
            # Assign a unique UDP port for this drone
            udp_port = self.udp_port_base + int(drone_id)
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_sockets[drone_id] = (udp_socket, udp_port)
            self.get_logger().info(f"Created UDP socket for drone {drone_id} on port {udp_port}")

    def telemetry_callback(self, msg: DroneTelemetry, drone_id: str) -> None:
        """Stores the latest telemetry data for each drone."""
        self.telemetry_data[drone_id] = {
            "percentage": msg.battery_percentage,
            "latitude": msg.global_position.x,
            "longitude": msg.global_position.y,
            "altitude": msg.global_position.z,
            "yaw": msg.yaw,
            "vel_x": msg.velocity.linear.x,
            "vel_y": msg.velocity.linear.y,
            "vel_z": msg.velocity.linear.z
        }

    def send_udp_data(self) -> None:
        """Sends telemetry data over separate UDP sockets for each drone."""
        for drone_id, data in self.telemetry_data.items():
            if drone_id in self.udp_sockets:
                udp_socket, udp_port = self.udp_sockets[drone_id]

                telemetry_json = json.dumps({
                    "drone_id": int(drone_id),
                    "percentage": data["percentage"],
                    "latitude": data["latitude"],
                    "longitude": data["longitude"],
                    "altitude": data["altitude"],
                    "yaw": data["yaw"],
                    "vel_x": data["vel_x"],
                    "vel_y": data["vel_y"],
                    "vel_z": data["vel_z"]
                })

                try:
                    udp_socket.sendto(telemetry_json.encode(), (self.udp_host, udp_port))
                    self.get_logger().debug(f"Sent UDP data for drone {drone_id}")
                except Exception as e:
                    self.get_logger().error(f"UDP send error for drone {drone_id}: {e}")

    def destroy_node(self):
        """Cleanup sockets before shutting down"""
        for sock, _ in self.udp_sockets.values():
            sock.close()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = TelemetryBroadcaster()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Shutting down gracefully...")
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == "__main__":
    main()