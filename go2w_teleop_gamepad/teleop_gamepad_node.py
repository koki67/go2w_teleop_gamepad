#!/usr/bin/env python3
# Copyright 2024 Koki Tanaka
# SPDX-License-Identifier: BSD-3-Clause
"""
go2w_teleop_gamepad — gamepad teleoperation for Unitree GO2-W.

Subscribes to sensor_msgs/Joy (from ros-humble-joy joy_node) and publishes
unitree_api/Request directly to the robot's Sport API topic.

Designed for the Logitech F710 in XInput mode (X/D switch set to X), but
works with any gamepad whose axis/button indices are configured via params.

Safety:
  - LB (deadman) must be held for any movement or action output.
  - Start fires Damp (soft e-stop) WITHOUT requiring deadman.
  - Watchdog publishes StopMove if no Joy message arrives for timeout_ms.
"""

import json
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from unitree_api.msg import Request, Response

# ── Unitree Sport API IDs (GO2-W compatible subset) ───────────────────────────
API_DAMP = 1001
API_STOP_MOVE = 1003
API_STAND_UP = 1004
API_STAND_DOWN = 1005
API_RECOVERY_STAND = 1006
API_MOVE = 1008
API_SPEED_LEVEL = 1015

# ── F710 XInput defaults (mode 1, light off) ─────────────────────────────────
DEFAULT_AXIS_LX = 0
DEFAULT_AXIS_LY = 1
DEFAULT_AXIS_RX = 3
DEFAULT_AXIS_RT = 5        # rest = -1.0, full press = +1.0

DEFAULT_BTN_A = 0
DEFAULT_BTN_B = 1
DEFAULT_BTN_X = 2
DEFAULT_BTN_LB = 4
DEFAULT_BTN_RB = 5
DEFAULT_BTN_START = 7


class TeleopGamepadNode(Node):
    """Reads Joy messages and publishes Unitree Sport API requests."""

    def __init__(self) -> None:
        super().__init__("go2w_teleop_gamepad_node")

        # ── Parameters ────────────────────────────────────────────────────────
        self._max_vx = self.declare_parameter("max_vx", 1.0).value
        self._max_vy = self.declare_parameter("max_vy", 0.6).value
        self._max_wz = self.declare_parameter("max_wz", 1.5).value
        self._scale_normal = self.declare_parameter("speed_scale_normal", 1.0).value
        self._scale_boost = self.declare_parameter("speed_scale_boost", 1.5).value
        self._timeout_ms = self.declare_parameter("timeout_ms", 500).value
        self._debounce_ms = self.declare_parameter("action_debounce_ms", 300).value
        self._dry_run = self.declare_parameter("dry_run", False).value
        self._boost_threshold = self.declare_parameter("boost_threshold", 0.5).value

        # Axis indices
        self._ax_lx = self.declare_parameter("axis_lx", DEFAULT_AXIS_LX).value
        self._ax_ly = self.declare_parameter("axis_ly", DEFAULT_AXIS_LY).value
        self._ax_rx = self.declare_parameter("axis_rx", DEFAULT_AXIS_RX).value
        self._ax_rt = self.declare_parameter("axis_rt", DEFAULT_AXIS_RT).value

        # Button indices
        self._btn_a = self.declare_parameter("button_a", DEFAULT_BTN_A).value
        self._btn_b = self.declare_parameter("button_b", DEFAULT_BTN_B).value
        self._btn_x = self.declare_parameter("button_x", DEFAULT_BTN_X).value
        self._btn_lb = self.declare_parameter("button_lb", DEFAULT_BTN_LB).value
        self._btn_rb = self.declare_parameter("button_rb", DEFAULT_BTN_RB).value
        self._btn_start = self.declare_parameter("button_start", DEFAULT_BTN_START).value

        if self._dry_run:
            self.get_logger().warn(
                "[DRY_RUN] active — requests will be logged but NOT published.")

        # ── Publisher / Subscriber ────────────────────────────────────────────
        self._req_pub = self.create_publisher(Request, "/api/sport/request", 10)
        self._joy_sub = self.create_subscription(Joy, "/joy", self._on_joy, 10)
        self._resp_sub = self.create_subscription(
            Response, "/api/sport/response", self._on_response, 10)

        # ── Watchdog timer (5 Hz) ─────────────────────────────────────────────
        self._watchdog_timer = self.create_timer(0.2, self._watchdog_callback)

        # ── State ─────────────────────────────────────────────────────────────
        self._prev_buttons: list = []
        self._last_joy_time: float = 0.0
        self._deadman_was_active: bool = False
        self._speed_level: int = 0
        self._last_trigger: dict = {}  # button_index -> monotonic timestamp
        self._watchdog_fired: bool = False

        self._print_banner()

    # ── Joy callback ──────────────────────────────────────────────────────────
    def _on_joy(self, msg: Joy) -> None:
        now = time.monotonic()
        self._last_joy_time = now
        self._watchdog_fired = False

        buttons = list(msg.buttons)
        axes = list(msg.axes)

        # Safely read values with bounds checking
        deadman = self._btn_val(buttons, self._btn_lb)

        # ── Start = Damp (no deadman required) ────────────────────────────────
        if self._rising_edge(buttons, self._btn_start):
            self._publish_or_log(
                self._make_request(API_DAMP),
                "Damp (e-stop via Start)")

        # ── Deadman released → stop everything ───────────────────────────────
        if self._deadman_was_active and not deadman:
            self._publish_or_log(
                self._make_request(API_STOP_MOVE),
                "StopMove (deadman released)")

        # ── With deadman held ─────────────────────────────────────────────────
        if deadman:
            # Movement from sticks
            lx = self._axis_val(axes, self._ax_lx)
            ly = self._axis_val(axes, self._ax_ly)
            rx = self._axis_val(axes, self._ax_rx)
            rt_raw = self._axis_val(axes, self._ax_rt)

            # LY: push forward = positive on GO2-W Jetson driver
            vx = ly
            vy = lx
            vyaw = rx

            # Clamp to [-1, 1]
            vx = max(-1.0, min(1.0, vx))
            vy = max(-1.0, min(1.0, vy))
            vyaw = max(-1.0, min(1.0, vyaw))

            # Boost: RT trigger rests at -1.0, fully pressed = +1.0
            rt_norm = (rt_raw + 1.0) / 2.0
            boost = rt_norm > self._boost_threshold
            scale = self._scale_boost if boost else self._scale_normal

            # Apply max velocities and scale
            vx *= self._max_vx * scale
            vy *= self._max_vy * scale
            vyaw *= self._max_wz * scale

            # Publish Move
            param = json.dumps({"x": round(vx, 4), "y": round(vy, 4),
                                "z": round(vyaw, 4)})
            self._publish_or_log(
                self._make_request(API_MOVE, param),
                f"Move vx={vx:.2f} vy={vy:.2f} wz={vyaw:.2f}"
                + (" [BOOST]" if boost else ""),
                debug=True)

            # ── Button actions (edge-triggered) ──────────────────────────────
            # A = RecoveryStand
            if self._rising_debounced(buttons, self._btn_a, now):
                self._publish_or_log(
                    self._make_request(API_RECOVERY_STAND),
                    "RecoveryStand (A)")

            # B = StandDown
            if self._rising_debounced(buttons, self._btn_b, now):
                self._publish_or_log(
                    self._make_request(API_STAND_DOWN),
                    "StandDown (B)")

            # X = StandUp
            if self._rising_debounced(buttons, self._btn_x, now):
                self._publish_or_log(
                    self._make_request(API_STAND_UP),
                    "StandUp (X)")

            # RB = SpeedLevel cycle
            if self._rising_debounced(buttons, self._btn_rb, now):
                self._speed_level = (self._speed_level + 1) % 3
                self._publish_or_log(
                    self._make_request(API_SPEED_LEVEL,
                                       json.dumps({"data": self._speed_level})),
                    f"SpeedLevel({self._speed_level}) (RB)")

        # ── Save state for next callback ──────────────────────────────────────
        self._deadman_was_active = deadman
        self._prev_buttons = buttons

    # ── Watchdog ──────────────────────────────────────────────────────────────
    def _watchdog_callback(self) -> None:
        if self._last_joy_time == 0.0:
            return  # no joy message received yet
        elapsed_ms = (time.monotonic() - self._last_joy_time) * 1000.0
        if elapsed_ms > self._timeout_ms and not self._watchdog_fired:
            self._watchdog_fired = True
            self._publish_or_log(
                self._make_request(API_STOP_MOVE),
                f"StopMove (watchdog: no Joy for {elapsed_ms:.0f}ms)")
            self._deadman_was_active = False

    # ── Sport API response ────────────────────────────────────────────────
    def _on_response(self, msg: Response) -> None:
        code = msg.header.status.code
        api_id = msg.header.identity.api_id
        if code != 0:
            self.get_logger().warn(
                f"Sport API rejected: api_id={api_id} code={code}")
        else:
            self.get_logger().debug(
                f"Sport API accepted: api_id={api_id}")

    # ── Helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _btn_val(buttons: list, idx: int) -> bool:
        """Safely read a button value."""
        if idx < len(buttons):
            return bool(buttons[idx])
        return False

    @staticmethod
    def _axis_val(axes: list, idx: int) -> float:
        """Safely read an axis value."""
        if idx < len(axes):
            return float(axes[idx])
        return 0.0

    def _rising_edge(self, buttons: list, idx: int) -> bool:
        """True if button just went from 0→1."""
        return (self._btn_val(buttons, idx)
                and not self._btn_val(self._prev_buttons, idx))

    def _rising_debounced(self, buttons: list, idx: int, now: float) -> bool:
        """Rising edge with debounce."""
        if not self._rising_edge(buttons, idx):
            return False
        last = self._last_trigger.get(idx, 0.0)
        if (now - last) * 1000.0 < self._debounce_ms:
            return False
        self._last_trigger[idx] = now
        return True

    @staticmethod
    def _make_request(api_id: int, parameter: str = "") -> Request:
        """Build a unitree_api/Request message."""
        req = Request()
        req.header.identity.api_id = api_id
        req.parameter = parameter
        return req

    def _publish_or_log(self, req: Request, description: str = "",
                        debug: bool = False) -> None:
        """Publish request or log it in dry_run mode."""
        if self._dry_run:
            if not debug:
                self.get_logger().info(
                    f"[DRY_RUN] api_id={req.header.identity.api_id}"
                    f"  param='{req.parameter}'  desc='{description}'")
        else:
            if debug:
                self.get_logger().debug(
                    f"Pub: api_id={req.header.identity.api_id}"
                    f"  param='{req.parameter}'  desc='{description}'")
            else:
                self.get_logger().info(
                    f"Pub: api_id={req.header.identity.api_id}"
                    f"  desc='{description}'")
            self._req_pub.publish(req)

    def destroy_node(self) -> None:
        """Stop movement on shutdown."""
        stop = self._make_request(API_STOP_MOVE)
        self._req_pub.publish(stop)
        self.get_logger().info("Shutdown: StopMove")
        super().destroy_node()

    # ── Banner ────────────────────────────────────────────────────────────────
    def _print_banner(self) -> None:
        B = "\033[1m"
        C = "\033[36m"
        Y = "\033[33m"
        R = "\033[31m"
        N = "\033[0m"
        lines = [
            "",
            f"{B}{C}+-- GO2-W Gamepad Teleoperation (F710) -------------------------+{N}",
            f"{B}{C}|{N}  Hold {B}{Y}LB{N} (deadman) for movement and actions                  {B}{C}|{N}",
            f"{B}{C}|{N}  Set F710 switch to {B}X{N} (XInput mode, indicator light OFF)       {B}{C}|{N}",
            f"{B}{C}+----------------------------------------------------------------+{N}",
            f"{B}{C}|{N} {B}MOVEMENT{N} (while holding LB)                                   {B}{C}|{N}",
            f"{B}{C}|{N}   Left stick  = forward/back (vx) + strafe (vy)               {B}{C}|{N}",
            f"{B}{C}|{N}   Right stick = yaw rotation (wz)                             {B}{C}|{N}",
            f"{B}{C}|{N}   RT trigger  = boost speed                                   {B}{C}|{N}",
            f"{B}{C}+----------------------------------------------------------------+{N}",
            f"{B}{C}|{N} {B}ACTIONS{N} (while holding LB, except Start)                      {B}{C}|{N}",
            f"{B}{C}|{N}   A = Recovery Stand       B = Stand Down                     {B}{C}|{N}",
            f"{B}{C}|{N}   X = Stand Up             RB = Speed Level cycle             {B}{C}|{N}",
            f"{B}{C}|{N}   {R}Start = DAMP (e-stop, no deadman needed){N}                   {B}{C}|{N}",
            f"{B}{C}+----------------------------------------------------------------+{N}",
            f"{B}{C}|{N} {B}PARAMS{N}  vx={self._max_vx:.1f}  vy={self._max_vy:.1f}"
            f"  wz={self._max_wz:.1f}"
            f"  scale={self._scale_normal:.1f}/{self._scale_boost:.1f}"
            f"  dry_run={self._dry_run}",
            f"{B}{C}+----------------------------------------------------------------+{N}",
            "",
        ]
        self.get_logger().info("\n".join(lines))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = TeleopGamepadNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
