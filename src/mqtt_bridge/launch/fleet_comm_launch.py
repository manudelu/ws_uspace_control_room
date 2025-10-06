from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():

    return LaunchDescription([
        Node(
            package='mqtt_bridge',
            executable='mqtt_ros_bridge',
            name='mqtt_ros_bridge'
        ),
        Node(
            package='mqtt_bridge',
            executable='mission_service_server',
            name='mission_service_server'
        ),
        Node(
            package='mqtt_bridge',
            executable='mission_mqtt_publisher',
            name='mission_mqtt_publisher'
        )
    ])
