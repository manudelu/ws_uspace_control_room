#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from pymavlink import mavutil
from drone_interfaces.srv import FetchMission, FetchAllMissions
from std_msgs.msg import String
import json
from typing import Dict, Any
import threading

class MissionServer(Node):
    def __init__(self):
        super().__init__('mission_server')

        self.drones: Dict[int, Dict[str, Any]] = {}

        # Subscribe to drone registrations
        self.drone_id_subscriber = self.create_subscription(
            String,
            '/drone_id',
            self.vehicle_id_callback,
            10
        )

        # Aggregator service
        self.aggregator_service = self.create_service(
            FetchAllMissions,
            '/fetch_missions',
            self.fetch_all_missions_callback
        )

        self.get_logger().info("Mission Server ready. Waiting for drones...")

    def vehicle_id_callback(self, msg: String) -> None:
        try:
            drone_id = int(msg.data)
            if drone_id >= 1 and drone_id not in self.drones:
                self.register_drone(drone_id)
                self.get_logger().info(f"Registered mission service for drone {drone_id}")
        except ValueError:
            self.get_logger().error(f"Invalid drone ID received: {msg.data}")

    def register_drone(self, drone_id: int) -> None:
        ns = '' if drone_id == 1 else f'px4_{drone_id-1}/'
        service_name = f'/{ns}fetch_mission'

        service = self.create_service(
            FetchMission,
            service_name,
            lambda request, response, id=drone_id: self.fetch_mission_callback(request, response, id)
        )

        # --- Open persistent MAVLink connection ---
        port = 14540 + (drone_id - 1)
        connection = mavutil.mavlink_connection(f'udp:127.0.0.1:{port}')
        try:
            connection.wait_heartbeat(timeout=5)
            self.get_logger().info(f"Persistent connection established with drone {drone_id}")
        except Exception as e:
            self.get_logger().error(f"Drone {drone_id} failed to connect: {e}")
            connection.close()
            connection = None

        self.drones[drone_id] = {
            'service': service,
            'connection': connection,
            'lock': threading.Lock()  # ensures thread-safe MAVLink access
        }

    def fetch_mission_callback(self, request, response, drone_id: int) -> FetchMission.Response:
        drone_info = self.drones.get(drone_id)
        if not drone_info or not drone_info["connection"]:
            response.success = False
            response.message = f"No active MAVLink connection for drone {drone_id}"
            response.waypoints = ""
            return response

        master = drone_info["connection"]

        with drone_info["lock"]:  # protect access
            try:
                # --- Flush old MAVLink messages ---
                while master.recv_match(blocking=False):
                    pass

                # --- Request mission list with retry ---
                retries = 3
                count_msg = None
                for attempt in range(retries):
                    master.mav.mission_request_list_send(
                        master.target_system,
                        master.target_component
                    )
                    count_msg = master.recv_match(type='MISSION_COUNT', blocking=True, timeout=2)
                    if count_msg:
                        break
                    else:
                        self.get_logger().warn(f"Drone {drone_id}: No mission count, retry {attempt+1}/{retries}")

                if not count_msg:
                    raise Exception("No mission count received after retries")

                self.get_logger().info(f"Drone {drone_id}: Found {count_msg.count} waypoints")

                # --- If no waypoints ---
                if count_msg.count == 0:
                    response.success = True
                    response.message = "No waypoints found"
                    response.waypoints = json.dumps([])
                    return response

                # --- Fetch all waypoints ---
                waypoints = []
                for seq in range(count_msg.count):
                    wp = None
                    for attempt in range(2):
                        master.mav.mission_request_int_send(
                            master.target_system,
                            master.target_component,
                            seq
                        )
                        wp = master.recv_match(type='MISSION_ITEM_INT', blocking=True, timeout=3)
                        if wp:
                            break
                        else:
                            self.get_logger().warn(f"Drone {drone_id}: Waypoint {seq} not received, retry {attempt+1}/2")

                    if not wp:
                        raise Exception(f"Failed to get waypoint {seq} after retries")

                    waypoints.append({
                        'seq': wp.seq,
                        'x': wp.x / 1e7,
                        'y': wp.y / 1e7,
                        'z': wp.z,
                        'command': wp.command
                    })

                response.success = True
                response.message = f"Got {len(waypoints)} waypoints for drone {drone_id}"
                response.waypoints = json.dumps(waypoints)

            except Exception as e:
                self.get_logger().error(f"Drone {drone_id} error: {str(e)}")
                response.success = False
                response.message = str(e)
                response.waypoints = ""
        return response

    def fetch_all_missions_callback(self, request, response):
        results = {}
        success = True

        # Decide which drones to fetch
        drone_ids = request.drone_ids if request.drone_ids else list(self.drones.keys())

        if not drone_ids:
            response.success = False
            response.message = "No drones registered"
            response.missions_json = "{}"
            return response

        for drone_id in drone_ids:
            if drone_id not in self.drones:
                results[str(drone_id)] = {"error": "Drone not registered"}
                success = False
                continue

            single_req = FetchMission.Request()
            single_res = FetchMission.Response()
            single_res = self.fetch_mission_callback(single_req, single_res, drone_id)

            if single_res.success:
                results[str(drone_id)] = json.loads(single_res.waypoints)
            else:
                results[str(drone_id)] = {"error": single_res.message}
                success = False

        response.success = success
        response.message = "Fetched missions" if success else "Some missions failed"
        response.missions_json = json.dumps(results)

        return response

def main(args=None):
    rclpy.init(args=args)
    node = MissionServer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Shutting down gracefully...")
    finally:
        node.destroy_node()
        for drone_id, info in node.drones.items():
            if info["connection"]:
                info["connection"].close()
                node.get_logger().info(f"Closed connection for drone {drone_id}")
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()