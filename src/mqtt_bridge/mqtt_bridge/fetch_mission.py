#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from pymavlink import mavutil
from drone_interfaces.srv import FetchMission
from std_msgs.msg import String
import json
from typing import Dict, Any, Optional

class MissionFetcher(Node):
    def __init__(self):
        super().__init__('mission_fetcher')
        
        # Dictionary to store drone services and connections
        self.drones: Dict[int, Dict[str, Any]] = {}
        
        # Setup drone registration subscriber
        self.drone_id_subscriber = self.create_subscription(
            String, 
            '/drone_id', 
            self.vehicle_id_callback, 
            10
        )
        
        self.get_logger().info("Mission Fetcher Server ready. Waiting for drone registrations...")

    def vehicle_id_callback(self, msg: String) -> None:
        """Handle new drone registration."""
        try:
            drone_id = int(msg.data)
            if drone_id >= 1 and drone_id not in self.drones:
                self.register_drone(drone_id)
                self.get_logger().info(f"Registered mission service for drone {drone_id}")
        except ValueError as e:
            self.get_logger().error(f"Invalid drone ID received: {msg.data}")

    def register_drone(self, drone_id: int) -> None:
        """Create service for a new drone."""
        # Determine service namespace
        ns = '' if drone_id == 1 else f'px4_{drone_id-1}/'
        service_name = f'/{ns}fmu/out/fetch_mission'
        
        # Create service
        service = self.create_service(
            FetchMission,
            service_name,
            lambda request, response, id=drone_id: self.fetch_mission_callback(request, response, id)
        )
        
        # Store drone info
        self.drones[drone_id] = {
            'service': service,
            'connection': None
        }

    def fetch_mission_callback(self, request, response, drone_id: int) -> FetchMission.Response:
        """Fetch mission for a specific drone."""
        try:
            # Connect to PX4 (different ports for different drones)
            port = 14540 + (drone_id - 1) 
            master = mavutil.mavlink_connection(f'udp:127.0.0.1:{port}')
            master.wait_heartbeat(timeout=5)
            self.get_logger().info(f"Connected to PX4 for drone {drone_id}")

            # Request mission list
            master.mav.mission_request_list_send(
                master.target_system,
                master.target_component
            )

            # Get mission count
            count_msg = master.recv_match(type='MISSION_COUNT', blocking=True, timeout=3)
            if not count_msg:
                raise Exception("No mission count received")
            
            self.get_logger().info(f"Drone {drone_id}: Found {count_msg.count} waypoints")

            # If no waypoints, return empty response
            if count_msg.count == 0:
                response.success = True
                response.message = "No waypoints found"
                response.waypoints = json.dumps([])
                return response

            # Fetch all waypoints
            waypoints = []
            for seq in range(count_msg.count):
                master.mav.mission_request_int_send(
                    master.target_system,
                    master.target_component,
                    seq
                )
                wp = master.recv_match(type='MISSION_ITEM_INT', blocking=True, timeout=2)
                if not wp:
                    raise Exception(f"Failed to get waypoint {seq}")
                
                waypoints.append({
                    'seq': wp.seq,
                    'x': wp.x / 1e7,  # Latitude
                    'y': wp.y / 1e7,  # Longitude
                    'z': wp.z         # Altitude
                })

            # Return success
            response.success = True
            response.message = f"Got {len(waypoints)} waypoints for drone {drone_id}"
            response.waypoints = json.dumps(waypoints)

        except Exception as e:
            self.get_logger().error(f"Drone {drone_id} error: {str(e)}")
            response.success = False
            response.message = str(e)
            response.waypoints = ""

        finally:
            if 'master' in locals():
                master.close()
        
        return response

    def __del__(self):
        """Cleanup on shutdown."""
        for drone_id in self.drones.keys():
            if self.drones[drone_id]['connection']:
                self.drones[drone_id]['connection'].close()

def main(args=None):
    rclpy.init(args=args)
    node = MissionFetcher()
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