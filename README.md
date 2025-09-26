# IoT-Enabled Control Room for Coordinated UAV Fleet Management

This repository provides an open-source framework for setting up a Control Room to coordinate fleets of UAVs using PX4 Autopilot, ROS 2 Humble, and AirSim/Unreal Engine.

Unlike many UAV frameworks that are simulation-only, this Control Room has been tested with real DJI enterprise drones, ensuring scalability, interoperability, and practical deployment in industrial and research environments.

## What is a Control Room?

The Control Room acts as a centralized *Command, Control & Communication (C3)* hub for both real and simulated UAVs.

It enables:
- Mission planning and fleet coordination acsross multiple UAVs
- Real-time telemetry monitoring from physical drones
- Digital Twin synchronization: each real drone is mirrored in a photorealistic 3D environment
- IoT-ready communication: MQTT protocol enables bi-directional data exchange with UAVs and external IoT devices

## Installation & Setup

This guide assumes:

- *Windows machine* → Unreal Engine (Cosys-AirSim + Cesium for Unreal) and QGroundControl
- *Linux machine (Ubuntu 22.04)* → PX4, ROS 2, Micro XRCE-DDS, and the Control Room

### Step1: Build Cosys-AirSim on Windows
--------------
*1. Install Unreal Engine 5.4*
* Download the *Epic Games Launcher*: https://store.epicgames.com/it/download
* Open the Epic Games Launcher and navigate to the *Unreal Engine* tab on the left sidebar.
* Click on the *Install* button on the top right and download *Unreal Engine 5.4*.

*2. Build Cosys-AirSim*
* Download *Visual Studio Community 2022*: https://visualstudio.microsoft.com/it/vs/community/
* Make sure to select *Desktop Development with C++* and the latest *Windows 10 SDK* (or *Windows 11 SDK* if you're on Windows 11).
* In the *Individual Components* tab, ensure the latest *.NET Framework SDK* is selected.
* Complete the installation of Visual Studio 2022.
*Important:* Make sure that you installed the latest version of Visual Studio 2022.
* Open *Developer Command Prompt for VS 2022*.
* Clone the Cosys-AirSim repository with submodules:
```
git clone --recurse-submodules https://github.com/Cosys-Lab/Cosys-AirSim.git
```
* Navigate to the Cosys-AirSim directory and run the build script:
```
cd Cosys-AirSim
build.cmd
```

*3. Setup the Blocks Environment for Cosys-AirSim*
* Navigate to `Cosys-AirSim\Unreal\Environments\Blocks` and open `Blocks.uproject` file. This will open Unreal Engine.
* Press the *Play* button in Unreal Editor and choose *No* when prompted about spawning a car or a multirotor.
* You'll see the multirotor spawning inside the BlocksV2 environment.

*4. Settings.json*

Navigate to `Documents\AirSim`, and copy this inside the `settings.json` file (depending on your own configuration you'll need to tweak these parameters, please refer to the [official documentation](https://cosys-lab.github.io/Cosys-AirSim/settings/))
```
{
    "SettingsVersion": 2.0,
    "SimMode": "Multirotor",
	"ViewMode": "FlyWithMe",
	"PawnPaths": {
		"DefaultQuadrotor": {"PawnBP": "Class'/AirSim/Blueprints/BP_MyPawn.BP_MyPawn_C'"}
	},
	"ClockType": "SteppableClock",
	"RpcEnabled": true,
    "Vehicles": {
        "Drone1": {
            "VehicleType": "PX4Multirotor",				
            "UseSerial": false,
			"LockStep": true,
            "UseTcp": true,                                                
            "TcpPort": 4560,
			"ControlPortLocal": 14540,
            "ControlPortRemote": 14580,
            "LocalHostIp": "0.0.0.0",
			"X": 0, "Y": 0, "Z": 0, "Yaw": 0,
			"Sensors":{
                "Barometer":{
                    "SensorType": 1,
                    "Enabled": true,
                    "PressureFactorSigma": 0.0001825
                }
            },
            "Parameters": {
                "NAV_RCL_ACT": 0,
                "NAV_DLL_ACT": 0,
                "COM_OBL_ACT": 1,
                "LPE_LAT": 44.063600,
                "LPE_LON": 8.026497
            }
        },
        "Drone2": {
            "VehicleType": "PX4Multirotor",				
            "UseSerial": false,
			"LockStep": true,
            "UseTcp": true,                                                
            "TcpPort": 4561,
			"ControlPortLocal": 14541,
            "ControlPortRemote": 14581,
            "LocalHostIp": "0.0.0.0",
			"X": 10, "Y": 0, "Z": -3, "Yaw": 0,
			"Sensors":{
                "Barometer":{
                    "SensorType": 1,
                    "Enabled": true,
                    "PressureFactorSigma": 0.0001825
                }
            },
            "Parameters": {
                "NAV_RCL_ACT": 0,
                "NAV_DLL_ACT": 0,
                "COM_OBL_ACT": 1
            }
        }
    },
    "OriginGeopoint": {
        "Latitude": 44.063600,
        "Longitude": 8.026497,
        "Altitude": 0.0
    }
}
```

### Step2: Initial Setup on Linux (Ubuntu 22.04)
-----------------

```bash
apt install sudo
sudo apt update
sudo apt-get install git-all
# Code requirements
python3 -m pip install paho-mqtt
pip install python-dotenv
```

*1. Install PX4 Autopilot*

```bash
git clone https://github.com/PX4/PX4-Autopilot.git --recursive
bash ./PX4-Autopilot/Tools/setup/ubuntu.sh --no-sim-tools
cd PX4-Autopilot/
make px4_sitl_default
```

*2. Configure PX4 for Cosys-AirSim*

Edit `.bashrc`:

```bash
nano ~/.bashrc
# Add at the end:
export PX4_SIM_HOST_ADDR=192.168.9.37    # <-- IP of the machine running Unreal Engine
source ~/.bashrc
```

*3. Update PX4*

```bash
cd PX4-Autopilot/
make clean
make distclean
git checkout v1.15.4      # Or another release
make submodulesclean
```

*4. Test PX4 ↔ AirSim communication*

* After launching the Unreal Engine simulation:

```bash
make px4_sitl_default none_iris
# or
./PX4-Autopilot/Tools/simulation/sitl_multiple_run.sh 1 
```

* In the PX4 console (only once, to enable multi-drone simulation):

```bash
param set UXRCE_DDS_KEY $((px4_instance+1)) 
```

### Step3: Install ROS 2 Humble
-----------------

```bash
sudo apt update && sudo apt install locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

sudo apt install software-properties-common
sudo add-apt-repository universe
sudo apt update && sudo apt install curl -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update && sudo apt upgrade -y
sudo apt install ros-humble-desktop
sudo apt install ros-dev-tools
pip install --user -U empy==3.3.4 pyros-genmsg setuptools

# Source ROS 2
source /opt/ros/humble/setup.bash
echo "source /opt/ros/humble/setup.bash" >> .bashrc
```

### Step4: Install Micro XRCE-DDS Agent
--------------

```bash
git clone -b ros2 https://github.com/eProsima/Micro-XRCE-DDS-Agent.git
cd Micro-XRCE-DDS-Agent
mkdir build && cd build
cmake ..
make
```

> **Fix CMakeLists.txt**  
If you get a `fastdds` version error ([issue](https://github.com/eProsima/Micro-XRCE-DDS-Agent/issues/370)), edit:
```cmake
set(_fastdds_tag v2.12.x) ➔ set(_fastdds_tag v2.13.x)
```

Install:

```bash
sudo make install
sudo ldconfig /usr/local/lib/
```

* Test PX4 ↔ Micro XRCE-DDS Agent

Terminal 1:

```bash
MicroXRCEAgent udp4 -p 8888
```

Terminal 2:

```bash
make px4_sitl_default none_iris
```

### Step5: Control Room Workspace Setup
--------------

```bash
mkdir -p ~/ws_uspace_control_room
git clone https://github.com/manudelu/ws_uspace_control_room.git --recursive
```

To keep `px4_msgs` message definitions in sync with PX4:

```bash
rm ~/ws_uspace_control_room/src/px4_msgs/msg/*.msg
cp ~/PX4-Autopilot/msg/*.msg ~/ws_uspace_control_room/src/px4_msgs/msg/
```

Build the workspace:

```bash
source /opt/ros/humble/setup.bash
colcon build
source install/local_setup.bash
```

### Step6: Final Test (Simulation)
--------------------

* Start the Unreal Engine simulation with Cosys-AirSim.

* Open 3 terminals:

    * *Terminal 1* – Run Micro XRCE-DDS Agent

        ```bash
        MicroXRCEAgent udp4 -p 8888
        ```
    * *Terminal 2* – Run PX4 SITL

        ```bash
        ./PX4-Autopilot/Tools/simulation/sitl_multiple_run.sh n   # n = number of drones (ex: 1)
        ```
    * *Terminal 3* – Run ROS 2 Offboard Example

        ```bash
        ros2 run px4_ros_com offboard_control
        ```

The drone should arm, take off to 5m, and hover indefinitely.

## Usage Workflow

* **Simulation Mode (software-in-the-loop)**

    * Launch Unreal Engine simulation with Cosys-AirSim.
    * Open 2 terminals:

        * *Terminal 1* – Launch Micro XRCE-DDS Agent and PX4 SITL (in this example, num_drone=2 instances of PX4)

            ```bash
            ros2 launch drone_control px4_instances_launch.py num_drones:=2
            ```
        * *Terminal 2* – Launch ROS2 Control Room nodes

            ```bash
            ros2 launch drone_control fleet_management_launch.py
            ```
    * Use QGroundControl to upload or draw missions.

* **Digital Twin Mode (hardware-in-the-loop)**

    * Ensure your drone has a companion onboard computer that publishes/receives MQTT messages (see *mqtt_ros_bridge.py*).
    * Start the Control Room as above.
    * You can plan missions in QGroundControl. 
    * Upload mission, but do NOT start it from QGroundControl.
    * Once uploaded, mission waypoints are intercepted by ROS2 (via MAVLink), processed, and republished over dedicated MQTT channels.
    * The Control Room then:
        * Dispatches the mission to the real UAV
        * Mirrors execution in the Digital Twin
        * Maintains fleet-wide synchronization in case of multi-UAV setup

This workflow turns QGroundControl into a front-end planner, while the Control Room handles execution, coordination, and IoT integration
