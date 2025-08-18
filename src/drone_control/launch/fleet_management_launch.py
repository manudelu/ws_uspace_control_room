from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    mqtt_bridge_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory('mqtt_bridge'),
                'launch',
                'fleet_comm_launch.py'
            )
        )
    )

    offboard_node = Node(
        package='drone_control',
        executable='offb_node',
        name='offboard_node',
        output='screen'
    )

    telemetry_broadcaster_node = Node(
        package='drone_control',
        executable='telemetry_broadcaster',
        name='telemetry_broadcaster',
        output='screen'
    )

    return LaunchDescription([
        mqtt_bridge_launch,
        offboard_node,
        telemetry_broadcaster_node,
    ])
