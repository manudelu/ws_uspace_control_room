#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from px4_msgs.msg import OffboardControlMode, TrajectorySetpoint, VehicleCommand, VehicleStatus, VehicleGlobalPosition, VehicleAttitude
from drone_interfaces.msg import DroneTelemetry
from std_msgs.msg import String
from typing import Dict, Any
import math
from drone_control.pid_controller import PIDController
from drone_control.lowpass_filter import LowPassFilter
from drone_control.drone_param_manager import PX4ParamManager

# Plot (debug)
import os
import csv
from datetime import datetime

def latlon_diff_to_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple:
    """
    Convert latitude and longitude differences to meters in north/east directions
    """
    R = 6371000.0 # Earth's radius in meters
    lat_diff_m = (lat2 - lat1) * math.pi/180 * R
    avg_lat = (lat1 + lat2) / 2.0 * math.pi/180
    lon_diff_m = (lon2 - lon1) * math.pi/180 * R * math.cos(avg_lat)
    return lat_diff_m, lon_diff_m

class OffboardControl(Node):
    """
    Node for controlling multiple vehicles in offboard mode using existing topics.
    """
    def __init__(self) -> None:
        super().__init__('offboard_control')

        # Configure QoS profile
        self.qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )

        self.drones: Dict[str, Dict[str, Any]] = {} 
        self.control_frequency = 10.0  # Hz 

        # Drone registration subscriber
        self.drone_id_subscriber = self.create_subscription(
            String, 
            '/drone_id', 
            self.vehicle_id_callback, 
            10
        )

        # Main Control timer  
        self.timer = self.create_timer(1/self.control_frequency, self.timer_callback)

        # Plot (debug)
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(log_dir, f"pid_log_{timestamp}.csv")
        self.csv_file = open(self.log_file, mode="w", newline="")
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow([
            "time", "drone_id",
            "sim_lat", "sim_lon", "sim_alt",
            "lat", "lon", "alt",
            "north_err", "east_err", "down_err",
        ])
        self.get_logger().info(f"Logging PID data to {self.log_file}")

    def vehicle_id_callback(self, msg: String) -> None:
        """Handle new drone registration."""
        try:
            drone_id = int(msg.data)
            if drone_id >= 1 and drone_id not in self.drones:
                self.register_drone(drone_id)
                self.get_logger().info(f"Registered new drone with ID: {drone_id}")
        except ValueError:
            self.get_logger().error(f"Invalid drone ID received: {msg.data}")

    def register_drone(self, drone_id: int) -> None:
        """Initialize all publishers and subscribers for a new drone."""
        self.drones[drone_id] = {
            'vehicle_status': None,
            'vx': 0.0, 'vy': 0.0, 'vz': 0.0,
            'lat': 0.0, 'lon': 0.0, 'alt': 0.0, 'yaw': 0.0,
            'sim_lat': 0.0, 'sim_lon': 0.0, 'sim_alt': 0.0, 'sim_yaw': 0.0,
            'publishers': None, 'subscribers': None,
            'params_configured': False,
            'param_manager': None,
            'prestreaming': True,
            'arming_sent': False,   
            'disarm_sent': False, 
        }

        # TODO: Tune PID parameters 
        self.drones[drone_id]['pid'] = PIDController(
            kp_vert=1.3, 
            kd_vert=0.4, 
            ki_vert=0.05,

            kp_horiz=0.2,#0.8, 
            kd_horiz=0.05, 
            ki_horiz=0.0,

            kp_yaw=1.2, 
            kd_yaw=0.0, 
            ki_yaw=0.0,

            integral_limit=5.0,
            alpha=0.7,           
            output_limit=3.0     
        )

        # LPF per drone 
        self.drones[drone_id]['lpf'] = LowPassFilter(
            cutoff=2.0,
            fs=self.control_frequency,
            order=2
        )

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
            'vehicle_sim_global_pose': self.create_subscription(
                VehicleGlobalPosition,
                f'/{ns}fmu/out/vehicle_global_position',
                lambda msg, id=drone_id: self.vehicle_sim_global_pose_callback(msg, id),
                self.qos_profile
            ),
            'vehicle_attitude': self.create_subscription(
                VehicleAttitude,
                f'/{ns}fmu/out/vehicle_attitude',
                lambda msg, id=drone_id: self.vehicle_attitude_callback(msg, id),
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
        drone = self.drones[drone_id]
        drone.update({
            'vx': msg.velocity.linear.x,
            'vy': msg.velocity.linear.y,
            'vz': msg.velocity.linear.z,
            'lat': msg.global_position.x,
            'lon': msg.global_position.y,
            'alt': msg.global_position.z,
            'yaw': msg.yaw,
            'status': msg.flight_status,
        })

        status = drone['vehicle_status']
        if status is None:
            return

        now = self.get_clock().now().nanoseconds / 1e9  # seconds
        last_arm_attempt = drone.get('last_arm_attempt', 0.0)

        # Configure params once
        if not drone['params_configured'] and hasattr(msg, 'drone_type'):
            self.configure_drone_params(drone_id, msg.drone_type)

        flight_status = getattr(msg, 'flight_status', None)
        # --- DISARM: flight_status == 0 ---
        if flight_status == 0:
            if status.arming_state == VehicleStatus.ARMING_STATE_ARMED and not drone.get('disarm_sent', False):
                self.get_logger().info(f"Telemetry flight_status==0 → sending disarm for drone {drone_id}")
                self.land(drone_id)
                drone['disarm_sent'] = True
                drone['arming_sent'] = False

        # --- ARM: flight_status == 1 ---
        elif flight_status == 1:
            # Only arm if PX4 is not already armed and we haven’t sent arm yet
            if status.arming_state != VehicleStatus.ARMING_STATE_ARMED and (now - last_arm_attempt > 2.0):
                self.get_logger().info(f"Telemetry flight_status==1 → Arming for drone {drone_id}")
                self.arm(drone_id)
                drone['arming_sent'] = True  # mark that we sent the arm command
                drone['last_arm_attempt'] = now

            # Engage offboard only if PX4 is already armed
            if status.arming_state == VehicleStatus.ARMING_STATE_ARMED:
                self.engage_offboard_mode(drone_id)

        # --- IN-FLIGHT: flight_status == 2 ---
        elif flight_status == 2:
            # Drone is in-flight; velocity commands can continue
            pass

    def configure_drone_params(self, drone_id: int, drone_type: str) -> None:
        """Configure PX4 parameters for a given drone type."""
        try:
            connection_url = f"udp:127.0.0.1:{14540 + (drone_id - 1)}"
            param_manager = PX4ParamManager(connection_url)
            param_manager.configure_drone(drone_type)
            self.drones[drone_id]['param_manager'] = param_manager
            self.drones[drone_id]['params_configured'] = True
            self.get_logger().info(f"PX4 parameters configured for drone {drone_id} ({drone_type})")
        except Exception as e:
            self.get_logger().error(f"Failed to configure PX4 parameters for drone {drone_id}: {e}")

    # Updated vehicle_status_callback: reset flags when PX4 reports actually disarmed
    def vehicle_status_callback(self, msg: VehicleStatus, drone_id: int) -> None:
        self.drones[drone_id]['vehicle_status'] = msg

        # Reset arming_sent only when PX4 has truly disarmed
        if msg.arming_state == VehicleStatus.ARMING_STATE_DISARMED:
            if self.drones[drone_id].get('arming_sent', False):
                self.get_logger().info(f"Drone {drone_id} reported disarmed → clearing arming flag")
            self.drones[drone_id]['arming_sent'] = False

        # Reset disarm_sent once PX4 reports disarmed
        if self.drones[drone_id].get('disarm_sent', False) and msg.arming_state == VehicleStatus.ARMING_STATE_DISARMED:
            self.drones[drone_id]['disarm_sent'] = False
    
    def vehicle_sim_global_pose_callback(self, msg: VehicleGlobalPosition, drone_id: int) -> None:
        """Store simulated local PX4 position (NED frame) and normalize altitude."""
        drone = self.drones[drone_id]

        # Initialize reference altitude on first callback
        if 'sim_alt_ref' not in drone:
            drone['sim_alt_ref'] = msg.alt

        drone['sim_lat'] = msg.lat  
        drone['sim_lon'] = msg.lon  
        drone['sim_alt'] = msg.alt - drone['sim_alt_ref']  

    def vehicle_attitude_callback(self, msg: VehicleAttitude, drone_id: int) -> None:
        drone = self.drones[drone_id]
        q0, q1, q2, q3 = msg.q[0], msg.q[1], msg.q[2], msg.q[3]
        drone['sim_yaw'] = math.atan2(2*(q0*q3 + q1*q2), 1 - 2*(q2*q2 + q3*q3))

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
        """Send land command."""
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
        msg.timestamp = self.get_clock().now().nanoseconds // 1000 
        self.drones[drone_id]['publishers']['offboard_control_mode'].publish(msg)

    def publish_velocity_setpoint(self, drone_id: int, velocity: dict = None) -> None:
        """Publish velocity commands."""
        vx, vy, vz, vw = velocity['x'], velocity['y'], -velocity['z'], velocity['yaw']

        drone = self.drones[drone_id]
        vx += drone['vx']
        vy += drone['vy']
        vz += drone['vz']

        msg = TrajectorySetpoint()
        msg.position = [float('nan')]*3
        msg.velocity = [vx, vy, vz]  # NED frame
        msg.yawspeed = vw
        msg.timestamp = self.get_clock().now().nanoseconds // 1000 
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
        msg.target_system = drone_id # Critical for multi-drone (https://docs.px4.io/main/en/ros2/multi_vehicle)
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        msg.timestamp = self.get_clock().now().nanoseconds // 1000
        self.drones[drone_id]['publishers']['vehicle_command'].publish(msg)

    def timer_callback(self) -> None:
        """Main control loop executed at fixed frequency."""
        dt = 1.0 / self.control_frequency
        now = self.get_clock().now().nanoseconds / 1e9  # Current time [s]

        for drone_id, drone in self.drones.items():
            if 'publishers' not in drone or drone.get('vehicle_status') is None:
                continue

            # Always publish heartbeat (keeps offboard alive)
            self.publish_offboard_control_heartbeat_signal(drone_id)

            # If drone is already in offboard + armed → send velocity
            if (drone['vehicle_status'].nav_state == VehicleStatus.NAVIGATION_STATE_OFFBOARD and drone['vehicle_status'].arming_state == VehicleStatus.ARMING_STATE_ARMED):
                pid = drone['pid']
                lpf = drone['lpf'] 

                # Apply LPF to measured positions
                lat_f = lpf.apply(drone['lat'], drone_id, 'lat')
                lon_f = lpf.apply(drone['lon'], drone_id, 'lon')
                alt_f = lpf.apply(drone['alt'], drone_id, 'alt')
                yaw_f = lpf.apply(drone['yaw'], drone_id, 'yaw')

                velocity_cmd, debug = pid.compute(
                    latitude=lat_f,
                    longitude=lon_f,
                    altitude=alt_f,
                    yaw=yaw_f,
                    sim_lat=drone['sim_lat'],
                    sim_lon=drone['sim_lon'],
                    sim_alt=drone['sim_alt'],
                    sim_yaw=drone['sim_yaw'],  
                    dt=dt
                )

                self.publish_velocity_setpoint(drone_id, velocity=velocity_cmd)
            else:
                self.publish_velocity_setpoint(drone_id, velocity={'x': 0.0, 'y': 0.0, 'z': 0.0, 'yaw': 0.0})

            # Log position differences
            lat_diff_m, lon_diff_m = latlon_diff_to_meters(drone['sim_lat'], drone['sim_lon'], drone['lat'], drone['lon'])
            alt_diff_m = drone['sim_alt'] - drone['alt']
            self.get_logger().info(f"[Drone{drone_id}] Sim vs Real Δpos → north={lat_diff_m:.2f}m, east={lon_diff_m:.2f}m, down={alt_diff_m:.2f}m")

            # Plot (debug)
            self.csv_writer.writerow([
                f"{now:.3f}", drone_id,
                drone['sim_lat'], drone['sim_lon'], drone['sim_alt'],
                drone['lat'], drone['lon'], drone['alt'],
                lat_diff_m, lon_diff_m, alt_diff_m,
            ])

def main(args=None):
    rclpy.init(args=args)
    controller = OffboardControl()
    try:
        rclpy.spin(controller)
    except KeyboardInterrupt:
        pass
    finally:
        controller.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()