# Control Room

## Configurazione iniziale

```bash
apt install sudo
sudo apt update
sudo apt-get install git-all
python3 -m pip install paho-mqtt
```

## Installazione di PX4 Autopilot

```bash
git clone https://github.com/PX4/PX4-Autopilot.git --recursive
bash ./PX4-Autopilot/Tools/setup/ubuntu.sh --no-sim-tools
cd PX4-Autopilot/
make px4_sitl_default
```

### Impostazioni per Cosys-AirSim

Modifica `.bashrc`:

```bash
nano ~/.bashrc
# Aggiungi alla fine:
export PX4_SIM_HOST_ADDR=192.168.9.37    # <-- IP della macchina sulla gira il simulatore (SmartAmbulance)
source ~/.bashrc
```

### Per aggiornare PX4:

```bash
cd PX4-Autopilot/
make clean
make distclean
git checkout v1.15.4      # O altra versione (al momento v.1.15.4)
make submodulesclean
```

### Test per vedere se PX4 e Cosys-AirSim comunicano:

Dopo aver lanciato la simulazione su Unreal Engine:

```bash
make px4_sitl_default none_iris
# oppure ./PX4-Autopilot/Tools/simulation/sitl_multiple_run.sh 1 
```

Nella console di PX4 (solo la prima volta per abilitare la simulazione multi drone):

```bash
param set UXRCE_DDS_KEY $((px4_instance+1)) 
```

## Installazine di ROS2 Humble

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
source /opt/ros/humble/setup.bash && echo "source /opt/ros/humble/setup.bash" >> .bashrc
```

## Installazione di Micro RC-DDS Agent

```bash
git clone -b ros2 https://github.com/eProsima/Micro-XRCE-DDS-Agent.git
cd Micro-XRCE-DDS-Agent
mkdir build && cd build
cmake ..
make
```

> **Fix CMakeLists.txt**  
In caso di errore di `fastdds`, modifica:
```cmake
set(_fastdds_tag v2.12.x) ➔ set(_fastdds_tag v2.13.x)
```

```bash
sudo make install
sudo ldconfig /usr/local/lib/
```

### Test per vedere se PX4 e Micro-XRCE-DDS comunicano

In un primo terminale:

```bash
MicroXRCEAgent udp4 -p 8888
```

In un secondo terminale:

```bash
make px4_sitl_default none_iris
```

# Workspace Setup

```bash
mkdir -p ~/ws_uspace_control_room
git clone https://github.com/manudelu/ws_uspace_control_room.git --recursive
```

Per mantenere le definizioni dei messaggi sincronizzate tra la versione installata di PX4 e la versione di px4_msgs:

```bash
rm ~/ws_uspace_control_room/src/px4_msgs/msg/*.msg
cp ~/PX4-Autopilot/msg/*.msg ~/ws_uspace_control_room/src/px4_msgs/msg/
```

Builda il workspace:

```bash
source /opt/ros/humble/setup.bash
colcon build
source install/local_setup.bash
```

# Test Finale

In un primo terminale, dopo aver lanciato la simulazione su Unreal Engine:

```bash
MicroXRCEAgent udp4 -p 8888
```

In un secondo terminale:

```bash
./PX4-Autopilot/Tools/simulation/sitl_multiple_run.sh 1  # n = 1 --> numero di veicoli
```

In un terzo terminale:

```bash
ros2 run px4_ros_com offboard_control
```

Il drone dovrebbe armarsi, ascendere di 5 metri, e rimanere in hovering all'infinito.