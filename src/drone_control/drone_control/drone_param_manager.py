#!/usr/bin/env python3
from pymavlink import mavutil


class PX4ParamManager:
    """
    PX4 Parameter Manager using pymavlink.
    Handles setting parameters for different drone types.
    """

    def __init__(self, connection_url: str):
        """
        Initialize MAVLink connection to a PX4 instance.
        Example: connection_url = "udp:127.0.0.1:14540"
        """
        self.master = mavutil.mavlink_connection(connection_url)
        self.master.wait_heartbeat()
        print(f"[PX4ParamManager] Connected to PX4 system {self.master.target_system}")

    def set_param(self, name: str, value: float, param_type: int = mavutil.mavlink.MAV_PARAM_TYPE_REAL32):
        """Send parameter to PX4 and wait for acknowledgment."""
        self.master.mav.param_set_send(
            self.master.target_system,
            self.master.target_component,
            name.encode('utf-8'),
            float(value),
            param_type
        )

        # Wait for PARAM_VALUE response
        ack = self.master.recv_match(type='PARAM_VALUE', blocking=True, timeout=2)
        if ack:
            param_id = ack.param_id
            if isinstance(param_id, bytes):
                param_id = param_id.decode('utf-8')
            param_id = param_id.strip('\x00')

            if param_id == name:
                print(f"[PX4ParamManager] {name} set to {ack.param_value}")
            else:
                print(f"[PX4ParamManager][WARN] ACK mismatch: expected {name}, got {param_id}")
        else:
            print(f"[PX4ParamManager][WARN] No ACK for {name}")

    def configure_drone(self, drone_type: str):
        """Apply PX4 parameter set based on drone type."""
        if drone_type == "M210" or drone_type == "M210 RTK" or drone_type == "M200":
            # https://www.dji.com/it/products/compare-m200-series
            print(f"[PX4ParamManager] Configuring parameters for {drone_type}...")
            self.set_param("MPC_YAWRAUTO_MAX", 150.0)   # deg/s
            self.set_param("MPC_Z_VEL_MAX_UP", 5.0)     # m/s
            self.set_param("MPC_Z_VEL_MAX_DN", 3.0)     # m/s
            self.set_param("MPC_XY_VEL_MAX", 22.5)      # m/s
        elif drone_type == "Mavic 3E" or drone_type == "Mavic 3T":
            # https://enterprise.dji.com/it/mavic-3-enterprise/specs
            print(f"[PX4ParamManager] Configuring parameters for {drone_type}...")
            self.set_param("MPC_YAWRAUTO_MAX", 200.0)
            self.set_param("MPC_Z_VEL_MAX_UP", 8.0)
            self.set_param("MPC_Z_VEL_MAX_DN", 6.0)
            self.set_param("MPC_XY_VEL_MAX", 21.0)
        elif drone_type == "M350 RTK":
            # https://enterprise.dji.com/it/matrice-350-rtk/specs
            print(f"[PX4ParamManager] Configuring parameters for {drone_type}...")
            self.set_param("MPC_YAWRAUTO_MAX", 100.0)
            self.set_param("MPC_Z_VEL_MAX_UP", 6.0)
            self.set_param("MPC_Z_VEL_MAX_DN", 7.0)
            self.set_param("MPC_XY_VEL_MAX", 23.0)
        else:
            print(f"[PX4ParamManager][WARN] Unknown drone type: {drone_type}")