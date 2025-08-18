import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'drone_control'

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
    description='Package for controlling a fleet of digital twin drones in offboard mode',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'offb_node = drone_control.offb_node:main',
            'telemetry_broadcaster = drone_control.telemetry_broadcaster:main',
        ],
    },
)
