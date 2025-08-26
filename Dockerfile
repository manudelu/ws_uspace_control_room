FROM ubuntu22-ldap:latest

# Set non-interactive mode and default locale
ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8

WORKDIR /root

SHELL ["/bin/bash", "-c"]

# Install system dependencies
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        sudo \
        git-all \
        gedit \
        terminator \
        inetutils-ping \
        python3 \
        python3-pip \
        locales \
        software-properties-common \
        curl && \
    locale-gen en_US.UTF-8 && \
    update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 && \
    rm -rf /var/lib/apt/lists/*

# Python dependencies
RUN python3 -m pip install --no-cache-dir \
    paho-mqtt \
    dotenv

# Clone PX4 and build
RUN git clone https://github.com/PX4/PX4-Autopilot.git --recursive && \
    ./PX4-Autopilot/Tools/setup/ubuntu.sh --no-sim-tools && \
    cd PX4-Autopilot && make px4_sitl_default && \
    make clean && make distclean && \
    git checkout v1.15.4 && \
    make submodulesclean

# Setup ROS2 Humble
RUN add-apt-repository universe -y && \
    curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
        http://packages.ros.org/ros2/ubuntu \
        $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | \
        tee /etc/apt/sources.list.d/ros2.list > /dev/null && \
    apt-get update && apt-get install -y --no-install-recommends \
        ros-humble-desktop \
        ros-dev-tools && \
    python3 -m pip install --no-cache-dir --user \
        empy==3.3.4 \
        pyros-genmsg \
        setuptools && \
    echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc && \
    rm -rf /var/lib/apt/lists/*

# Build Micro XRCE-DDS Agent
RUN git clone -b ros2 https://github.com/eProsima/Micro-XRCE-DDS-Agent.git && \
    cd Micro-XRCE-DDS-Agent && \
    sed -E -i "s|set\(\s*_fastdds_tag\s*v?2\.12\.x\s*\)|set(_fastdds_tag 2.13.x)|g" ./CMakeLists.txt && \
    mkdir build && cd build && cmake .. && \
    make -j$(nproc) && make install && \
    ldconfig /usr/local/lib/

# PX4 Environment variable
RUN echo "export PX4_SIM_HOST_ADDR=192.168.9.37" >> ~/.bashrc