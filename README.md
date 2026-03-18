# go2w_teleop_gamepad

ROS 2 Humble package for controlling a **Unitree GO2-W** robot with a **Logitech F710** wireless gamepad.

Reads joystick input via the ROS 2 `joy` driver and publishes `unitree_api/Request` messages directly to `/api/sport/request`.

## Requirements

- ROS 2 Humble
- [`ros-humble-joy`](https://index.ros.org/p/joy/) — joystick driver
- [`unitree_api`](https://github.com/unitreerobotics/unitree_ros2) — Unitree message definitions
- Logitech F710 wireless gamepad (or any gamepad supported by the Linux `joydev` / `xpad` driver)

## Hardware Setup

1. Plug the F710 USB dongle into your PC.
2. Set the F710's **X/D switch to X** (XInput mode — the indicator light should be OFF).
3. Press the Logitech button on the gamepad to pair.
4. Verify the device appears:

   ```bash
   ls /dev/input/js0
   ```

   > **Tip:** If `js0` does not appear, try `sudo modprobe xpad` and check `dmesg | tail` for detection messages.

5. If running inside Docker, mount the input devices:

   ```bash
   docker run ... -v /dev/input:/dev/input:ro ...
   ```

   The [go2w-docker-dev](https://github.com/koki67/go2w-docker-dev) devcontainer already includes this mount.

## Build

```bash
cd ~/ros2_ws
colcon build --symlink-install --packages-select go2w_teleop_gamepad
source install/setup.bash
```

## Usage

### Dry Run (safe testing — logs commands, sends nothing to the robot)

```bash
ros2 launch go2w_teleop_gamepad teleop_gamepad.launch.py dry_run:=true
```

### Live

```bash
ros2 launch go2w_teleop_gamepad teleop_gamepad.launch.py
```

### Launch Arguments

| Argument | Default | Description |
|---|---|---|
| `device_id` | `0` | Joystick device index (`/dev/input/js<N>`) |
| `params_file` | built-in YAML | Path to a custom parameters file |
| `dry_run` | `false` | Log commands instead of publishing |

## Controls

Hold **LB** (deadman switch) for all movement and actions. Releasing LB immediately stops the robot.

### Movement (while holding LB)

| Input | Action |
|---|---|
| Left stick | Forward/back + strafe |
| Right stick | Yaw rotation |
| RT trigger | Boost speed (1.5x) |

### Actions (while holding LB)

| Button | Action |
|---|---|
| A | RecoveryStand |
| B | StandDown |
| X | BalanceStand |
| Y (hold) | HandStand (active while held) |
| RB | Cycle speed level (0 / 1 / 2) |
| Back | Toggle obstacle avoidance |
| D-pad up/down | Cycle gait (TrotRun / StaticWalk / FreeWalk) |

### Emergency Stop

| Button | Action |
|---|---|
| **Start** | **Damp (e-stop)** — works WITHOUT deadman |

## Safety Features

- **Deadman switch** — LB must be held; releasing it sends `StopMove`
- **Watchdog** — if no gamepad input for 500 ms (e.g. dongle disconnected), the robot stops automatically
- **Debounce** — button actions are debounced (300 ms) to prevent accidental double-triggers
- **Dry-run mode** — test the full control flow without sending commands to the robot

## Parameters

All parameters can be customized via the YAML config file ([`config/teleop_gamepad_params.yaml`](config/teleop_gamepad_params.yaml)):

| Parameter | Default | Description |
|---|---|---|
| `max_vx` | 1.0 | Max forward/back velocity (m/s) |
| `max_vy` | 0.6 | Max strafe velocity (m/s) |
| `max_wz` | 1.5 | Max yaw rate (rad/s) |
| `speed_scale_normal` | 1.0 | Normal speed multiplier |
| `speed_scale_boost` | 1.5 | Boost speed multiplier (RT held) |
| `timeout_ms` | 500 | Watchdog timeout (ms) |
| `action_debounce_ms` | 300 | Button debounce interval (ms) |
| `dry_run` | false | Log-only mode |

Axis and button indices can also be remapped for other gamepads — see the YAML file for details.

## License

Apache-2.0
