# Dockerfile for go2w_teleop_gamepad — robot-side deployment
#
# Runs on the Unitree GO2-W's Jetson Orin NX (ARM64).
# Reads a Logitech F710 gamepad and publishes Sport API requests
# directly to /api/sport/request via CycloneDDS.
#
# Build context is the repository root (one level above this file):
#   docker build -f docker/Dockerfile .
#
# Or use the provided docker-compose.yml.

FROM ros:humble-ros-base

# ── System dependencies ────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
      # CycloneDDS RMW (must match Unitree internal stack)
      ros-humble-rmw-cyclonedds-cpp \
      # Required by unitree_api message generation
      ros-humble-rosidl-generator-dds-idl \
      # Joystick driver: reads /dev/input/jsN, publishes sensor_msgs/Joy
      ros-humble-joy \
      # colcon build system
      python3-colcon-common-extensions \
      git \
    && rm -rf /var/lib/apt/lists/*

# ── Clone unitree_ros2 for message definitions (unitree_api) ─────────────────
RUN git clone --depth 1 https://github.com/koki67/unitree_ros2.git \
      /ros2_ws/src/unitree_ros2 \
    && rm -rf /ros2_ws/src/unitree_ros2/.git

# ── Copy this package ─────────────────────────────────────────────────────────
# Build context = repository root
COPY . /ros2_ws/src/go2w_teleop_gamepad

WORKDIR /ros2_ws

# ── Build only the required packages ──────────────────────────────────────────
# --packages-up-to builds go2w_teleop_gamepad + transitive deps (unitree_api)
RUN /bin/bash -c "\
    source /opt/ros/humble/setup.bash && \
    colcon build --packages-up-to go2w_teleop_gamepad \
    "

# ── Entrypoint ────────────────────────────────────────────────────────────────
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["ros2", "launch", "go2w_teleop_gamepad", "teleop_gamepad.launch.py"]
