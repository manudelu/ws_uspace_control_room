from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    num_drones_arg = DeclareLaunchArgument(
        'num_drones',
        default_value='2',
        description='Number of PX4 SITL drones to launch'
    )

    num_drones = LaunchConfiguration('num_drones')

    # Micro XRCE Agent
    microxrce_agent = ExecuteProcess(
        cmd=['MicroXRCEAgent', 'udp4', '-p', '8888'],
        name='microxrce_agent',
        output='screen'
    )

    # PX4 multiple drone SITL
    sitl_runner = ExecuteProcess(
        cmd=['/root/PX4-Autopilot/Tools/simulation/sitl_multiple_run.sh', num_drones],
        name='px4_sitl',
        output='screen'
    )

    return LaunchDescription([
        num_drones_arg,
        microxrce_agent,
        sitl_runner
    ])
