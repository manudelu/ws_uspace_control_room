FROM ubuntu:22.04

# Set noninteractive frontend for apt
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

WORKDIR /root

# Update and install basic tools
RUN apt update && apt upgrade -y \
    && apt install -y --no-install-recommends \
        git \
        sudo \
        curl \
        locales \
        vim \
        nano \
        gedit \
        terminator \
        inetutils-ping \
        python3 \
        python3-pip \
        software-properties-common \
    && apt clean \
    && rm -rf /var/lib/apt/lists/*

# Set locale
RUN locale-gen en_US.UTF-8 \
    && update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

# Install ROS2 Humble
RUN add-apt-repository universe -y \
    && curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" > /etc/apt/sources.list.d/ros2.list \
    && apt update && apt install -y ros-humble-desktop ros-dev-tools \
    && pip install --user -U empy==3.3.4 pyros-genmsg setuptools

# Source ROS2 setup
RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc

# Clone PX4 Autopilot
RUN git clone https://github.com/PX4/PX4-Autopilot.git --recursive
WORKDIR /root/PX4-Autopilot

# Setup PX4 environment and build SITL
RUN git checkout v1.15.4 \
    && ./Tools/setup/ubuntu.sh --no-sim-tools \
    && make px4_sitl_default

# Clone and build Micro XRCE-DDS Agent
WORKDIR /root
RUN git clone -b ros2 https://github.com/eProsima/Micro-XRCE-DDS-Agent.git
WORKDIR /root/Micro-XRCE-DDS-Agent
RUN sed -E -i "s|set\(\s*_fastdds_tag\s*v?2\.12\.x\s*\)|set(_fastdds_tag 2.13.x)|g" ./CMakeLists.txt \
    && mkdir build && cd build && cmake .. && make -j$(nproc) && make install \
    && ldconfig /usr/local/lib/

WORKDIR /root

# Set PX4 simulation host address as an environment variable (users can override)
ENV PX4_SIM_HOST_ADDR=127.0.0.1
RUN echo "export PX4_SIM_HOST_ADDR=${PX4_SIM_HOST_ADDR}" >> ~/.bashrc

# Install Control Room dependencies
RUN python3 -m pip install --no-cache-dir paho-mqtt websockets "numpy<2.0" python-dotenv

# Default command
CMD ["/bin/bash"]