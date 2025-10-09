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

## Unreal Engine Environment 

The Unreal Engine 5.4 environment is maintained in a separate repository, clone it somewhere on your machine: 
```bash
git clone https://github.com/manudelu/RaiseUAV.git
```
- In this repo, the Cosys-AirSim plugin is already included, so the environment should work out of the box without rebuilding the plugin.
- All additional setup, plugins, or environment-specific code is documented in the environment repo README.

## Installation & Setup

This guide assumes:

- *Windows machine* → Unreal Engine (Cosys-AirSim + Cesium for Unreal) and QGroundControl
- *Linux machine (Ubuntu 22.04)* → PX4, ROS 2, Micro XRCE-DDS, and the Control Room

<details> 

<summary><strong>Step1 - Build Cosys-AirSim</strong></summary>

*1. Install Unreal Engine 5.4*
* Download the *Epic Games Launcher*: https://store.epicgames.com/it/download
* Open it and navigate to the *Unreal Engine* tab (left sidebar).
* Click on the *Install* button on the top right and select *Unreal Engine 5.4*.

*2. Install and Configure Visual Studio 2022*
* Download *Visual Studio Community 2022*: https://visualstudio.microsoft.com/it/vs/community/
* During the setup, enable the following components:
    * *Desktop Development with C++*
    * *MSVC v14.38 (C++ toolset)* 
    * The latest version of *Windows 10 or 11 SDK*
    * The latest version of *.NET Framework SDK*
* Complete the installation of Visual Studio 2022.

> *Important:* Make sure Visual Studio 2022 is fully updated before proceeding.

*3. Clone and Build Cosys-AirSim (Optional if you cloned our environment)*
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

*4. Test Cosys-AirSim*
* Navigate to `Cosys-AirSim\Unreal\Environments\Blocks` and open `Blocks.uproject` file. This will open Unreal Engine.
* Press the *Play* button in Unreal Editor and choose *No* when prompted about spawning a car or a multirotor.
* You'll see the multirotor spawning inside the Blocks environment.
* On first launch, a default `/AirSim` folder is created in your `Documents\` directory containing a `settings.json` file.

> **Using Cosys-AirSim in your own Unreal project:** If you want to integrate Cosys-AirSim into your own Unreal project, copy the Plugins/AirSim folder from the Cosys-AirSim repository and drop it into the Plugins folder of your project. This ensures the plugin is available without rebuilding the original repository.

</details>

<details> 

<summary><strong>Step2 - Install and Configure PX4 SITL</strong></summary>

Initial System Setup

```bash
apt install sudo
sudo apt update
sudo apt-get install git-all
```

*1. Clone and Build PX4 Autopilot*

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
```

Add the following line at the end:
```bash
export PX4_SIM_HOST_ADDR=<UNREAL_ENGINE_HOST_IP>   # Replace this with the IP address of the machine running Unreal Engine
```

Apply the change:
```bash
source ~/.bashrc
```

*3. Update/Rebuild PX4 (Optional but Recommended)*

```bash
cd PX4-Autopilot/
make clean
make distclean
git checkout v1.15.4      # Version confirmed to work reliably
make submodulesclean
make px4_sitl_default
```

*4. Configure AirSim settings.json (Windows Side)*
Copy the `/AirSim` folder from this repository into your `Documents\` directory (Windows), replacing the existing one. This folder contains the `settings.json` file and a helper Python script to automate drone configuration based on a CSV file.

The script will:
* Update or generate drone entries in `settings.json`.
* Set correct Local X/Y/Z positions based on GPS coordinates.
* Set the first drone as origin reference.
* Automatically increase ports and add new PX4Multirotor instances if more drones are defined in the CSV than currently exist.

> Depending on your configuration, you may still need to verify LocalHostIp, TcpPort, ControlPortLocal, and ControlPortRemote depending on your local network setup. For reference, see the [official documentation](https://cosys-lab.github.io/Cosys-AirSim/settings/).

*5. Test PX4 ↔ AirSim communication*

* After launching the Unreal Engine simulation:

```bash
make px4_sitl_default none_iris
# or (multi-drone setup)
./PX4-Autopilot/Tools/simulation/sitl_multiple_run.sh n   # n = number of drones (ex: 1)
```

* In the PX4 console (only once, to enable multi-drone simulation), if you're running multiple PX4 instances, set unique communication keys:

```bash
param set UXRCE_DDS_KEY $((px4_instance+1)) 
```

> At this stage, AirSim should respond to PX4 SITL commands, and the drone(s) should spawn and respond to MAVLink traffic.

</details>

<details> 

<summary><strong>Step3 - Install and Configure QGroundControl</strong></summary>

*1. Download and Install QGroundControl*

Visit the official website [QGroundControl](https://docs.qgroundcontrol.com/master/en/qgc-user-guide/getting_started/download_and_install.html) and download the latest version for your platform.  

*2. Configure Communication Links*
* Open QGroundControl and go to *Application Settings → Comm Links*.  
* Click *Add* to create a new communication link for each drone.  
* Use the following settings for each link:
    - *Name:* Drone1, Drone2, …  
    - *Type:* UDP  
    - *Port:* 14580 (for Drone1; increment by 1 for each additional drone)  
    - *Server Address:* `<PX4_MACHINE_IP>`    
> `<PX4_MACHINE_IP>` is the IP address of the machine running PX4 SITL.  

*3. Verify Connection*

After configuring, QGroundControl should show the drones as connected and display telemetry data. You can now monitor and control the drones from the QGC interface.

> QGroundControl must be started **after** PX4 SITL and the simulation are up so it can detect the drones.

</details>

<details> 

<summary><strong>Step4 - Install ROS 2 Humble</strong></summary>

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
</details>

<details> 

<summary><strong>Step5 - Install Micro XRCE-DDS Agent (Required for PX4 ↔ ROS 2 Bridge)</strong></summary>

*1. Clone and Build the Agent*
```bash
git clone -b ros2 https://github.com/eProsima/Micro-XRCE-DDS-Agent.git
cd Micro-XRCE-DDS-Agent
mkdir build && cd build
cmake ..
make
```

> **Fix CMakeLists.txt**  
If you encounter a `fastdds` version error ([issue](https://github.com/eProsima/Micro-XRCE-DDS-Agent/issues/370)), edit the `CMakeLists.txt`:
```cmake
set(_fastdds_tag v2.12.x) ➔ set(_fastdds_tag v2.13.x)
```

*2. Install the Agent*

```bash
sudo make install
sudo ldconfig /usr/local/lib/
```

*3. Test PX4 ↔ Micro XRCE-DDS Agent Communication*

Terminal 1 - Start Micro XRCE-DDS Agent:

```bash
MicroXRCEAgent udp4 -p 8888
```

Terminal 2 - Launch PX4 SITL:

```bash
make px4_sitl_default none_iris
```

> If the setup is correct, you should see Client connected messages in the Micro XRCE-DDS Agent console when PX4 starts.

</details>

<details> 

<summary><strong>Step6 - Control Room Workspace Setup</strong></summary>

*1. Create Workspace and Clone Repository*
```bash
mkdir -p ~/ws_uspace_control_room
git clone https://github.com/manudelu/ws_uspace_control_room.git --recursive
```

*2. Install Python Dependencies*
```bash
python3 -m pip install paho-mqtt python-dotenv websockets "numpy<2.0"
```

*3. Synchronize PX4 Messages*
To keep `px4_msgs` message definitions in sync with your PX4 installation:

```bash
rm ~/ws_uspace_control_room/src/px4_msgs/msg/*.msg
cp ~/PX4-Autopilot/msg/*.msg ~/ws_uspace_control_room/src/px4_msgs/msg/
```

*4. Build the workspace:*

```bash
source /opt/ros/humble/setup.bash
colcon build
source install/local_setup.bash
```

</details>

<details> 

<summary><strong>Step7 - Final Communication Test</strong></summary>

*1. Start the Unreal Engine simulation with Cosys-AirSim*

*2. Open 3 terminals*

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

> The drone should arm, take off to 5m, and hover indefinitely.

</details>

## Usage Workflow

* **Simulation Mode (software-in-the-loop)**

    * Prepare the AirSim configuration by running the helper Python script (`Documents/AirSim/update_settings.py`). This script generates or updates the `settings.json` file with drone positions based on the starting positions provided in your CSV file.
    * Start Unreal Engine and launch the simulation.
    * Use the provided `launch_all.sh` script to automatically build and source the workspace, start PX4 SITL, Micro XRCE-DDS Agent, ROS 2 Control Room nodes, and other necessary services. Internally, the script performs the following steps:
        * Build the workspace:
            ```bash
            colcon build
            source install/setup.bash
            ```
        * Start MQTT → WebSocket bridge:
            ```bash
            python3 src/mqtt_bridge/mqtt_bridge/websocket.py 
            ```
        * Launch Micro XRCE-DDS Agent and PX4 SITL (in this example, num_drone=2 instances of PX4)
            ```bash
            ros2 launch drone_control px4_instances_launch.py num_drones:=2
            ```
        * Launch ROS2 Control Room nodes
            ```bash
            ros2 launch drone_control fleet_management_launch.py
            ```
    * Simulate drone operation
        * *Mission testing via QGroundControl (QGC):*
        QGC allows you to design and visualize drone missions, but it is limited to simulation within the GUI. No telemetry is published to the Control Room in this mode.

        * **Full telemetry simulation via MQTT:**
        The system can simulate actual drone telemetry using the same MQTT message format as in `mqtt_ros_bridge.py`. This simulates the real behavior of drones publishing telemetry in a hardware-in-the-loop scenario, allowing you to test the Control Room and fleet management software as if real drones were operating.

* **Digital Twin Mode (hardware-in-the-loop)**

    * Ensure your real drone (e.g., DJI Mavic 3E) has a companion onboard companion computer capable of publishing and receiving MQTT messages (see `src/mqtt_bridge/mqtt_bridge/mqtt_ros_bridge.py`).
    * Start the Control Room following the same procedure as in Simulation Mode.
    * As the drone moves, it publishes telemetry via MQTT.
    * You can plan missions in QGroundControl (QGC):
        * Upload the mission to the drone, but do *NOT* start it from QGC.
        * Once uploaded, mission waypoints are intercepted by ROS2 via MAVLink, processed, and republished over dedicated MQTT channels.
    * The Control Room then:
        * Dispatches the mission commands to the real UAV.
        * Mirrors execution in the Digital Twin environment.
        * Maintains fleet-wide synchronization in multi-UAV setups.

> This workflow transforms QGroundControl into a front-end mission planner, while the Control Room manages execution, coordination, and IoT integration.

**Note:** To connect the Control Room to the MQTT broker, create a `.env` file in the workspace root with the following structure:
```bash
MQTT_BROKER=<BROKER_IP>
MQTT_PORT=<BROKER_PORT>
MQTT_USERNAME=<USERNAME>
MQTT_PASSWORD=<PASSWORD>
```

## Code Explanation