# go2w_teleop_gamepad

ROS 2 package for controlling a **Unitree GO2-W** (wheeled) robot with a **Logitech F710** wireless gamepad.

The package reads joystick input via the ROS 2 `joy` driver and publishes `unitree_api/Request` messages to the robot's Sport API topic (`/api/sport/request`). It is designed to run directly on the robot's onboard **Jetson Orin NX** via Docker, communicating with the robot over its internal Ethernet (`eth0`, 192.168.123.x) using CycloneDDS.

## Overview

```
F710 Gamepad  --(USB dongle)-->  Jetson Orin NX (Docker container)
                                   joy_node  -->  /joy topic
                                   teleop_gamepad_node  -->  /api/sport/request
                                                              |
                                                              v
                                                         GO2-W Sport API
```

Two ROS 2 nodes run inside the container:

1. **joy_node** (from `ros-humble-joy`) — reads `/dev/input/jsN` and publishes `sensor_msgs/Joy`
2. **teleop_gamepad_node** — subscribes to `/joy`, maps stick/button inputs to Sport API commands, and publishes `unitree_api/Request`

## Requirements

### Hardware

- **Unitree GO2-W** robot (wheeled variant)
- **Logitech F710** wireless gamepad with USB dongle (or any Linux-compatible gamepad using `joydev` / `xpad` driver)

### Software (handled by Docker image)

- ROS 2 Humble
- [`ros-humble-joy`](https://index.ros.org/p/joy/) — joystick driver
- [`unitree_api`](https://github.com/unitreerobotics/unitree_ros2) — Unitree message definitions
- CycloneDDS RMW implementation

## Gamepad Setup

1. Set the F710's **X/D switch to X** (XInput mode). The indicator light on the gamepad should be **OFF**.
2. Press the Logitech button on the gamepad to turn it on.
3. Plug the F710 USB dongle into the Jetson (or your PC for development).
4. Verify the device appears:

   ```bash
   ls /dev/input/js*
   ```

   You should see `/dev/input/js0` (or `js1`, etc.).

   > **Tip:** If no `js` device appears, try `sudo modprobe xpad` and check `dmesg | tail` for detection messages.

## Robot Deployment (Docker on Jetson Orin NX)

This is the recommended way to run this package. Running on the robot's onboard Jetson eliminates WiFi latency and DDS discovery issues — all communication stays local on `eth0`.

### Prerequisites

- Docker and Docker Compose installed on the Jetson
- This repository cloned onto the Jetson (with the `unitree_ros2` submodule):

  ```bash
  git clone https://github.com/koki67/go2w-docker-dev.git
  cd go2w-docker-dev
  git submodule update --init --recursive
  ```

### Build the Docker Image

```bash
cd ros2_ws/src
docker compose -f go2w_teleop_gamepad/docker/docker-compose.yml build
```

> **Note:** On some Jetson setups the Docker client version is newer than the daemon. If you see `client version 1.53 is too new`, prefix all `docker` commands with:
> ```bash
> export DOCKER_API_VERSION=1.43
> ```

### Run

**Step 1 — Dry-run first** (logs commands but sends nothing to the robot):

```bash
DRY_RUN=true docker compose -f go2w_teleop_gamepad/docker/docker-compose.yml up
```

Verify the banner appears and button presses show up in the logs. Press Ctrl+C to stop.

**Step 2 — Live** (sends commands to the robot):

```bash
docker compose -f go2w_teleop_gamepad/docker/docker-compose.yml up -d
```

**Check logs:**

```bash
docker logs -f go2w_teleop_gamepad
```

**Stop:**

```bash
docker compose -f go2w_teleop_gamepad/docker/docker-compose.yml down
```

### Environment Variables

Set these on the host before `docker compose up`, or place them in a `.env` file next to `docker-compose.yml`.

| Variable | Default | Description |
|---|---|---|
| `DRY_RUN` | `false` | `true` to log commands without publishing to the robot |
| `DEVICE_ID` | `0` | Joystick device index — maps to `/dev/input/js<N>` |

### Single USB Port Workflow

The Jetson Orin NX has only **one USB-A port**. The gamepad dongle does not need to be plugged in when the container starts — the entrypoint will wait for it.

1. SSH into the Jetson (or connect a keyboard dongle to start a terminal)
2. Start the container:
   ```bash
   docker compose -f go2w_teleop_gamepad/docker/docker-compose.yml up -d
   ```
3. Check the logs — you will see:
   ```
   Waiting for /dev/input/js0 — plug in the gamepad dongle ...
   ```
4. Unplug the keyboard dongle (if using one) and plug in the F710 dongle
5. The container detects the device and launches the teleop automatically:
   ```
   Gamepad detected: /dev/input/js0
   ```
6. Monitor with `docker logs -f go2w_teleop_gamepad`

## Controls

Hold **LB** (deadman switch) for all movement and actions. Releasing LB immediately stops the robot.

### Movement (while holding LB)

| Input | Action |
|---|---|
| Left stick up/down | Forward / backward |
| Left stick left/right | Strafe left / right |
| Right stick left/right | Yaw rotation |
| RT trigger | Boost speed (1.5x) |

### Actions (while holding LB)

| Button | Action | Sport API ID |
|---|---|---|
| A | RecoveryStand — stand up from any position | 1006 |
| B | StandDown — sit down | 1005 |
| X | StandUp — switch to normal standing mode | 1004 |
| RB | Cycle speed level (0 / 1 / 2) | 1015 |

### Emergency Stop (no deadman required)

| Button | Action | Sport API ID |
|---|---|---|
| **Start** | **Damp** — soft e-stop, all motors go limp | 1001 |

### Typical Use-Case Flow

1. **LB + A** (RecoveryStand) — robot stands up from any position
2. **LB + X** (StandUp) — switch to normal standing mode
3. **LB + left stick** — move around
4. **LB + B** (StandDown) — robot sits down

> **Note:** StandDown (B) only works after StandUp (X) has been executed at least once in the current session. This is a Unitree SDK limitation, not specific to this package.

## Safety Features

| Feature | Description |
|---|---|
| **Deadman switch (LB)** | Must be held for any movement or action. Releasing LB sends `StopMove` immediately. |
| **Watchdog timer** | If no gamepad input arrives for 500 ms (e.g. dongle disconnected, gamepad turned off), the robot stops automatically. |
| **Button debounce** | Action buttons are debounced (300 ms) to prevent accidental double-triggers. |
| **Damp without deadman** | The Start button fires Damp (e-stop) regardless of whether LB is held — always accessible. |
| **Dry-run mode** | Test the full control flow without sending any commands to the robot. |
| **Shutdown stop** | When the node shuts down (Ctrl+C, container stop), it sends a final `StopMove` command. |

## Parameters

All parameters can be customized via the YAML config file ([`config/teleop_gamepad_params.yaml`](config/teleop_gamepad_params.yaml)):

### Velocity and Speed

| Parameter | Default | Description |
|---|---|---|
| `max_vx` | `1.0` | Max forward/backward velocity (m/s) |
| `max_vy` | `0.6` | Max strafe velocity (m/s) |
| `max_wz` | `1.5` | Max yaw rate (rad/s) |
| `speed_scale_normal` | `1.0` | Speed multiplier in normal mode |
| `speed_scale_boost` | `1.5` | Speed multiplier when RT trigger is held |
| `boost_threshold` | `0.5` | RT trigger normalized threshold (0-1) to activate boost |

### Safety

| Parameter | Default | Description |
|---|---|---|
| `timeout_ms` | `500` | Watchdog timeout — stops robot if no Joy message for this duration |
| `action_debounce_ms` | `300` | Minimum time between repeated button actions (ms) |
| `dry_run` | `false` | Log commands instead of publishing to the robot |

### Axis and Button Mapping

These can be overridden for gamepads with different axis/button indices. The defaults are for the F710 in XInput mode (X/D switch set to X, indicator light OFF).

| Parameter | Default | Description |
|---|---|---|
| `axis_lx` | `0` | Left stick horizontal axis |
| `axis_ly` | `1` | Left stick vertical axis |
| `axis_rx` | `3` | Right stick horizontal axis |
| `axis_rt` | `5` | RT trigger axis (rest = -1.0, full press = +1.0) |
| `button_a` | `0` | A button — RecoveryStand |
| `button_b` | `1` | B button — StandDown |
| `button_x` | `2` | X button — StandUp |
| `button_lb` | `4` | LB button — deadman switch |
| `button_rb` | `5` | RB button — speed level cycle |
| `button_start` | `7` | Start button — Damp (e-stop) |

To find the correct indices for your gamepad, run:

```bash
ros2 run joy joy_node
# In another terminal:
ros2 topic echo /joy
```

Press buttons and move sticks to see which indices change.

## Native Build (without Docker)

If you want to run directly on a machine with ROS 2 Humble installed (e.g. inside the go2w-docker-dev devcontainer):

```bash
cd ros2_ws
colcon build --symlink-install --packages-select go2w_teleop_gamepad
source install/setup.bash
```

### Launch

```bash
# Dry run (safe testing)
ros2 launch go2w_teleop_gamepad teleop_gamepad.launch.py dry_run:=true

# Live
ros2 launch go2w_teleop_gamepad teleop_gamepad.launch.py
```

### Launch Arguments

| Argument | Default | Description |
|---|---|---|
| `device_id` | `0` | Joystick device index (`/dev/input/js<N>`) |
| `params_file` | built-in YAML | Path to a custom parameters file |
| `dry_run` | `false` | Log commands instead of publishing |

## Troubleshooting

| Problem | Solution |
|---|---|
| No `/dev/input/js*` device | Check dongle is plugged in. Try `sudo modprobe xpad`. Check `dmesg \| tail`. |
| `joy_node` opens wrong device | Set `DEVICE_ID` (Docker) or `device_id` launch arg. Run `ls /dev/input/js*` to find the right index. |
| Robot doesn't move | Make sure you are holding **LB** (deadman). Check `docker logs` for Sport API response errors. |
| StandDown doesn't work | Execute **StandUp** (LB + X) at least once first. This is a Unitree SDK requirement. |
| Docker: `client version too new` | `export DOCKER_API_VERSION=1.43` before running docker commands. |
| Container waiting forever for device | Verify the dongle is plugged in and `ls /dev/input/js*` shows a device on the **host**. |
| DDS topics not visible | Ensure `network_mode: host` in docker-compose and CycloneDDS is pinned to `eth0`. |

## ROS 2 Topics

| Topic | Type | Direction | Description |
|---|---|---|---|
| `/joy` | `sensor_msgs/Joy` | Subscribe | Joystick input from `joy_node` |
| `/api/sport/request` | `unitree_api/Request` | Publish | Sport API commands to the robot |
| `/api/sport/response` | `unitree_api/Response` | Subscribe | Sport API acknowledgements (logged) |

## Package Structure

```
go2w_teleop_gamepad/
  go2w_teleop_gamepad/
    teleop_gamepad_node.py   # Main teleop node
  config/
    teleop_gamepad_params.yaml  # Default parameters
  docker/
    Dockerfile               # Robot-side Docker image
    docker-compose.yml        # Docker Compose for deployment
    entrypoint.sh             # ROS 2 sourcing + device wait
  launch/
    teleop_gamepad.launch.py  # Launches joy_node + teleop node
  package.xml
  setup.py
```

## License

Apache-2.0
