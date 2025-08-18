#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from drone_interfaces.msg import DroneTelemetry 
import tkinter as tk
from tkinter import ttk
from typing import Dict, Any
import threading
import signal
import sys

class BatteryStatusGUI(Node):
    def __init__(self):
        super().__init__('battery_status_gui')
        self._closed = False 
        
        self.subscribers: Dict[str, Any] = {}
        self.battery_data: Dict[str, Dict[str, float]] = {}

        # Subscribe to /drone_id
        self.drone_id_sub = self.create_subscription(
            String,
            '/drone_id',
            self.drone_id_callback,
            10
        )

        # GUI setup
        self.root = tk.Tk()
        self.root.title("Drone Battery Status Monitor")
        self.root.geometry("800x400")
        self.root.configure(bg="#f0f0f0")

        self.title_label = ttk.Label(
            self.root,
            text="Drone Fleet Battery Status",
            font=("Helvetica", 16, "bold"),
            background="#f0f0f0"
        )
        self.title_label.pack(pady=10)

        self.frame = ttk.Frame(self.root, padding="10")
        self.frame.pack(fill=tk.BOTH, expand=True)

        self.drone_widgets: Dict[str, Dict[str, tk.Widget]] = {}

        self.style = ttk.Style()
        self.style.configure("green.Horizontal.TProgressbar", background="green")
        self.style.configure("red.Horizontal.TProgressbar", background="red")

        # periodic update
        self.update_gui()

        # hook window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def drone_id_callback(self, msg: String) -> None:
        """Handle new drone registration."""
        drone_id = msg.data
        telemetry_topic = f"fleet/drone{drone_id}/telemetry"

        if drone_id not in self.subscribers:
            self.subscribers[drone_id] = self.create_subscription(
                DroneTelemetry,
                telemetry_topic,
                lambda msg, id=drone_id: self.telemetry_callback(msg, id),
                10
            )
            self.get_logger().info(f"Subscribed to telemetry for drone {drone_id}")
            self.add_drone_row(drone_id)

    def add_drone_row(self, drone_id: str) -> None:
        """Add a new row in the GUI for a drone."""
        drone_frame = ttk.Frame(self.frame)
        drone_frame.pack(fill=tk.X, pady=5)

        drone_label = ttk.Label(drone_frame, text=f"Drone {drone_id}", font=("Helvetica", 12))
        drone_label.grid(row=0, column=0, padx=10, sticky=tk.W)

        progress_bar = ttk.Progressbar(drone_frame, orient=tk.HORIZONTAL, length=100, mode="determinate")
        progress_bar.grid(row=0, column=1, padx=10)

        percentage_label = ttk.Label(drone_frame, text="0%", font=("Helvetica", 10))
        percentage_label.grid(row=0, column=2, padx=10)

        voltage_label = ttk.Label(drone_frame, text="Voltage: N/A", font=("Helvetica", 10))
        voltage_label.grid(row=0, column=3, padx=10)

        current_label = ttk.Label(drone_frame, text="Current: N/A", font=("Helvetica", 10))
        current_label.grid(row=0, column=4, padx=10)

        capacity_label = ttk.Label(drone_frame, text="Capacity: N/A", font=("Helvetica", 10))
        capacity_label.grid(row=0, column=5, padx=10)

        self.drone_widgets[drone_id] = {
            "progress_bar": progress_bar,
            "percentage_label": percentage_label,
            "voltage_label": voltage_label,
            "current_label": current_label,
            "capacity_label": capacity_label
        }

    def telemetry_callback(self, msg: DroneTelemetry, drone_id: str) -> None:
        self.battery_data[drone_id] = {
            'voltage': msg.battery_voltage,
            'current': msg.battery_current,
            'percentage': msg.battery_percentage,
            'capacity': msg.battery_capacity
        }

        if msg.battery_percentage < 20:
            self.show_low_battery_warning(drone_id, msg.battery_percentage)

    def show_low_battery_warning(self, drone_id: str, percentage: float) -> None:
        """Show a warning popup for low battery."""
        if hasattr(self, f"low_battery_popup_{drone_id}"):
            return

        popup = tk.Toplevel(self.root)
        popup.title("Low Battery Alert")
        popup.geometry("350x150")
        popup.configure(bg="red")

        warning_message = f"Warning: Drone {drone_id} has low battery ({percentage}%)!"
        label = tk.Label(popup, text=warning_message, font=("Helvetica", 12, "bold"), bg="red")
        label.pack(pady=20)

        dismiss_button = tk.Button(popup, text="Dismiss", command=popup.destroy, font=("Helvetica", 10))
        dismiss_button.pack(pady=10)

        setattr(self, f"low_battery_popup_{drone_id}", popup)
        popup.protocol("WM_DELETE_WINDOW", lambda: self.on_popup_close(drone_id, popup))

    def on_popup_close(self, drone_id: str, popup: tk.Toplevel) -> None:
        """Handle popup close event."""
        delattr(self, f"low_battery_popup_{drone_id}")
        popup.destroy()

    def update_gui(self) -> None:
        """Update the GUI with the latest battery data."""
        if self._closed:
            return

        for drone_id, data in self.battery_data.items():
            voltage = data['voltage']
            current = data['current']
            percentage = data['percentage']
            capacity = data['capacity']

            progress_bar = self.drone_widgets[drone_id]["progress_bar"]
            progress_bar["value"] = percentage

            percentage_label = self.drone_widgets[drone_id]["percentage_label"]
            percentage_label.config(text=f"{percentage}%")

            if percentage < 25:
                progress_bar["style"] = "red.Horizontal.TProgressbar"
            else:
                progress_bar["style"] = "green.Horizontal.TProgressbar"

            self.drone_widgets[drone_id]["voltage_label"].config(text=f"Voltage: {voltage/1000:.2f} V")
            self.drone_widgets[drone_id]["current_label"].config(text=f"Current: {current:.0f} mA")
            self.drone_widgets[drone_id]["capacity_label"].config(text=f"Capacity: {capacity:.0f} mAh")

        self.root.after(1000, self.update_gui)

    def on_close(self):
        """Unified shutdown handler"""
        if self._closed:
            return
        self._closed = True

        self.get_logger().info("Shutting down battery status GUI...")
        try:
            self.destroy_node()
        except Exception:
            pass
        if rclpy.ok():
            rclpy.shutdown()
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        """Run the GUI main loop."""
        self.root.mainloop()

def main(args=None):
    rclpy.init(args=args)
    gui_node = BatteryStatusGUI()

    spin_thread = threading.Thread(target=rclpy.spin, args=(gui_node,), daemon=True)
    spin_thread.start()

    signal.signal(signal.SIGINT, lambda sig, frame: gui_node.on_close())

    try:
        gui_node.run()
    finally:
        gui_node.on_close()
        spin_thread.join(timeout=2)

if __name__ == "__main__":
    main()