from setuptools import find_packages, setup
from glob import glob

package_name = "go2w_teleop_gamepad"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages",
         [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch",
         glob("launch/*.launch.py")),
        (f"share/{package_name}/config",
         glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Koki Tanaka",
    maintainer_email="tanaka.koki.t6r@research.f-rei.go.jp",
    description="Gamepad teleoperation node for Unitree GO2-W.",
    license="BSD-3-Clause",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "teleop_gamepad = go2w_teleop_gamepad.teleop_gamepad_node:main",
        ],
    },
)
