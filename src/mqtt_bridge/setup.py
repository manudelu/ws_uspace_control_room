import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'mqtt_bridge'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='root',
    maintainer_email='manueldelucchi@dartseng.it',
    description='MQTT-ROS topic bridge',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
          'mqtt_ros_bridge = mqtt_bridge.mqtt_ros_bridge:main',
          'fetch_mission = mqtt_bridge.fetch_mission:main',
        ],
    },
)
