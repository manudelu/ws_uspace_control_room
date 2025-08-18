#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from px4_msgs.msg import OffboardControlMode, TrajectorySetpoint, VehicleCommand, VehicleStatus
from drone_interfaces.msg import DroneTelemetry
from std_msgs.msg import String
from typing import Dict, Any


class OffboardControl(Node):
    """Node for controlling multiple vehicles in offboard mode using existing topics."""

    def __init__(self) -> None:
        super().__init__('offboard_control')

        # Configure QoS profile
        self.qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )

        # Dictionary to store drone data
        self.drones: Dict[str, Dict[str, Any]] = {} 
        self.control_frequency = 10.0  # Hz 

        # Setup drone registration subscriber
        self.drone_id_subscriber = self.create_subscription(
            String, 
            '/drone_id', 
            self.vehicle_id_callback, 
            10
        )

        # Main Control timer  
        self.timer = self.create_timer(1/self.control_frequency, self.timer_callback)

    def vehicle_id_callback(self, msg: String) -> None:
        """Handle new drone registration."""
        drone_id = int(msg.data)
        if drone_id >= 1 and drone_id not in self.drones:
            self.register_drone(drone_id)
            self.get_logger().info(f"Registered new drone with ID: {drone_id}")

    def register_drone(self, drone_id: int) -> None:
        """Initialize all publishers and subscribers for a new drone."""
        # Initialize drone data structure
        self.drones[drone_id] = {
            # Drone state
            'vehicle_status': None,
            'offboard_counter': 0,
            # Telemetry data
            'vx': 0.0,
            'vy': 0.0,
            'vz': 0.0,
            'yawspeed': 0.0,
            'timestamp': 0.0,
            # Communication interfaces
            'publishers': None,
            'subscribers': None
        }

        # Determine topic namespace
        ns = '' if drone_id == 1 else f'px4_{drone_id-1}/'

        # Create subscribers
        subscribers = {
            'vehicle_telemetry': self.create_subscription(
                DroneTelemetry, 
                f'/fleet/drone{drone_id}/telemetry',
                lambda msg, id=drone_id: self.vehicle_telemetry_callback(msg, id),
                10
            ),
            'vehicle_status': self.create_subscription(
                VehicleStatus, 
                f'/{ns}fmu/out/vehicle_status',
                lambda msg, id=drone_id: self.vehicle_status_callback(msg, id),
                self.qos_profile
            ),
        }

        # Create publishers
        publishers = {       
            'offboard_control_mode': self.create_publisher(
                OffboardControlMode, 
                f'/{ns}fmu/in/offboard_control_mode', 
                self.qos_profile
            ),
            'trajectory_setpoint': self.create_publisher(
                TrajectorySetpoint, 
                f'/{ns}fmu/in/trajectory_setpoint', 
                self.qos_profile
            ),
            'vehicle_command': self.create_publisher(
                VehicleCommand, 
                f'/{ns}fmu/in/vehicle_command', 
                self.qos_profile
            ),
        }

        self.drones[drone_id]['subscribers'] = subscribers
        self.drones[drone_id]['publishers'] = publishers

    def vehicle_telemetry_callback(self, msg: DroneTelemetry, drone_id: int) -> None:
        """Update drone telemetry data."""
        drone = self.drones[drone_id]
        drone.update({
            'vx': msg.velocity.linear.x,
            'vy': msg.velocity.linear.y,
            'vz': msg.velocity.linear.z,
            'yawspeed': msg.velocity.angular.z,
            'timestamp': msg.timestamp
        })
        
    def vehicle_status_callback(self, msg: VehicleStatus, drone_id: int) -> None:
        """Callback function for vehicle_status topic subscriber."""
        self.drones[drone_id]['vehicle_status'] = msg

    def arm(self, drone_id: int) -> None:
        """Send an arm command to the vehicle."""
        self.publish_vehicle_command(
            drone_id, 
            VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 
            param1=1.0
        )
        self.get_logger().info(f"Arm command sent to drone {drone_id}")

    def disarm(self, drone_id: int) -> None:
        """Send a disarm command to the vehicle."""
        self.publish_vehicle_command(
            drone_id, 
            VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 
            param1=0.0
        )
        self.get_logger().info(f"Disarm command sent to drone {drone_id}")
    
    def engage_offboard_mode(self, drone_id: int) -> None:
        """Switch to offboard mode."""
        self.publish_vehicle_command(
            drone_id, 
            VehicleCommand.VEHICLE_CMD_DO_SET_MODE, 
            param1=1.0, 
            param2=6.0
        )
        self.get_logger().info(f"Offboard mode engaged for drone {drone_id}")

    def land(self, drone_id: int) -> None:
        """Switch to land mode."""
        self.publish_vehicle_command(
            drone_id, 
            VehicleCommand.VEHICLE_CMD_NAV_LAND
        )
        self.get_logger().info(f"Land command sent to drone {drone_id}")

    def publish_offboard_control_heartbeat_signal(self, drone_id: int) -> None:
        """Publish offboard control mode."""
        msg = OffboardControlMode()
        msg.position = False
        msg.velocity = True
        msg.acceleration = False
        msg.attitude = False
        msg.body_rate = False
        msg.timestamp = self.get_clock().now().nanoseconds // 1000 # drone['timestamp']
        self.drones[drone_id]['publishers']['offboard_control_mode'].publish(msg)

    def publish_velocity_setpoint(self, drone_id: int):
        """Publish velocity commands."""
        drone = self.drones[drone_id]
        msg = TrajectorySetpoint()
        msg.position = [float('nan')]*3
        msg.velocity = [drone['vy'], drone['vx'], -drone['vz']]  # NED frame
        msg.yawspeed = drone['yawspeed']
        msg.timestamp = self.get_clock().now().nanoseconds // 1000 # drone['timestamp']
        self.drones[drone_id]['publishers']['trajectory_setpoint'].publish(msg)

    def publish_vehicle_command(self, drone_id: int, command, **params) -> None:
        """Send vehicle command."""
        msg = VehicleCommand()
        msg.command = command
        msg.param1 = params.get("param1", 0.0)
        msg.param2 = params.get("param2", 0.0)
        msg.param3 = params.get("param3", 0.0)
        msg.param4 = params.get("param4", 0.0)
        msg.param5 = params.get("param5", 0.0)
        msg.param6 = params.get("param6", 0.0)
        msg.param7 = params.get("param7", 0.0)
        msg.target_system = drone_id  # Critical for multi-drone (https://docs.px4.io/main/en/ros2/multi_vehicle)
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        msg.timestamp = self.get_clock().now().nanoseconds // 1000 # drone['timestamp']
        self.drones[drone_id]['publishers']['vehicle_command'].publish(msg)

    def timer_callback(self) -> None:
        """Main control loop executed at fixed frequency."""
        for drone_id, drone in self.drones.items():
            if 'publishers' not in drone or drone.get('vehicle_status') is None:
                continue

            self.publish_offboard_control_heartbeat_signal(drone_id)

            if drone['offboard_counter'] == 10:
                self.engage_offboard_mode(drone_id)
                self.arm(drone_id)

            if drone['vehicle_status'].nav_state == VehicleStatus.NAVIGATION_STATE_OFFBOARD:
                self.publish_velocity_setpoint(drone_id)
            
            if drone['offboard_counter'] < 11:
                drone['offboard_counter'] += 1

def main(args=None):
    rclpy.init(args=args)
    controller = OffboardControl()
    try:
        rclpy.spin(controller)
    except KeyboardInterrupt:
        pass
    finally:
        controller.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()