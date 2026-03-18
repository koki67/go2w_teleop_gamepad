#!/bin/bash
# Docker entrypoint: source ROS 2 and workspace overlays, then exec CMD.
set -e

source /opt/ros/humble/setup.bash
source /ros2_ws/install/setup.bash

# Wait for joystick device (supports plugging gamepad in after container start).
# On the Jetson Orin NX there is only one USB-A port, so the operator may need
# to start the container first (via keyboard/SSH) and plug the gamepad in later.
# The /dev/input bind mount shares the host's devtmpfs — new device files
# created by the kernel after container start are visible immediately.
DEV="/dev/input/js${DEVICE_ID:-0}"
if [ ! -e "$DEV" ]; then
  echo "Waiting for ${DEV} — plug in the gamepad dongle ..."
  while [ ! -e "$DEV" ]; do sleep 1; done
fi
echo "Gamepad detected: ${DEV}"

exec "$@"
