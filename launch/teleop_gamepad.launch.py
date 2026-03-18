#!/usr/bin/env python3
# Copyright 2024 Koki Tanaka
# SPDX-License-Identifier: BSD-3-Clause
"""Launch file for GO2-W gamepad teleoperation.

Launches:
  1. joy_node       — reads the gamepad and publishes sensor_msgs/Joy
  2. teleop_gamepad — subscribes to Joy and publishes Sport API requests
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory("go2w_teleop_gamepad")
    default_params = os.path.join(pkg_dir, "config", "teleop_gamepad_params.yaml")

    return LaunchDescription([
        # ── Launch arguments ──────────────────────────────────────────────────
        DeclareLaunchArgument(
            "device_id", default_value="0",
            description="Joystick device index (/dev/input/js<N>)"),
        DeclareLaunchArgument(
            "params_file", default_value=default_params,
            description="Path to gamepad teleop parameters YAML"),
        DeclareLaunchArgument(
            "dry_run", default_value="false",
            description="Log commands instead of publishing (safe testing)"),

        # ── joy_node (from ros-humble-joy) ────────────────────────────────────
        Node(
            package="joy",
            executable="joy_node",
            name="joy_node",
            parameters=[{
                "device_id": LaunchConfiguration("device_id"),
                "deadzone": 0.05,
                "autorepeat_rate": 50.0,
                "coalesce_interval_ms": 1,
            }],
            output="screen",
        ),

        # ── go2w_teleop_gamepad_node ──────────────────────────────────────────
        Node(
            package="go2w_teleop_gamepad",
            executable="teleop_gamepad",
            name="go2w_teleop_gamepad_node",
            parameters=[
                LaunchConfiguration("params_file"),
                {"dry_run": LaunchConfiguration("dry_run")},
            ],
            output="screen",
        ),
    ])
