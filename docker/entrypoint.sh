#!/bin/bash
# Docker entrypoint: source ROS 2 and workspace overlays, then exec CMD.
set -e

source /opt/ros/humble/setup.bash
source /ros2_ws/install/setup.bash

exec "$@"
