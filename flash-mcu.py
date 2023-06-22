#!env python3
import shlex
import subprocess
import sys
import os
import argparse
from typing import Optional

from dataclasses import dataclass


@dataclass
class Args:
    mcu: str
    firmware_path: str
    tool: Optional[str]
    start: Optional[str]
    dryrun: bool


def get_platformio_package_path(package: str) -> str:
    package_path = os.path.expanduser(
        os.path.join("~", ".platformio", "packages", package)
    )
    if not os.path.exists(package_path):
        print(f"PlatformIO package {package} is not found")
        sys.exit(1)
    return package_path


def get_platformio_package_bin_path(package: str, executable: str) -> str:
    package_path = get_platformio_package_path(package)
    bin_path = os.path.join(package_path, "bin", executable)
    if not os.path.exists(bin_path):
        print(f"PlatformIO package {package} does not have {executable}")
        sys.exit(1)
    return bin_path


def detect_openocd_path() -> tuple[str, str]:
    if os.path.exists("/usr/local/bin/openocd") and os.path.exists(
        "/usr/local/share/openocd"
    ):
        return "/usr/local/bin/openocd", "/usr/local/share/openocd"

    return (
        get_platformio_package_path("tool-openocd"),
        get_platformio_package_bin_path("tool-openocd", "openocd"),
    )


def flash_stm32(args: Args):
    openocd_bin, openocd_root = detect_openocd_path()

    mcu = args.mcu.lower()

    if args.start:
        start = args.start
    else:
        start = "0x8000000"

    if args.tool:
        tool = args.tool
    else:
        tool = "cmsis-dap"
    print(f"tool using {tool}")

    mcu_series = [
        "stm8s003",
        "stm8s103",
        "stm8s105",
        "stm32c0x",
        "stm32f0x",
        "stm32f1x",
        "stm32f2x",
        "stm32f3x",
        "stm32f4x",
        "stm32f7x",
        "stm32g0x",
        "stm32g4x",
        "stm32h7x",
    ]
    detected_mcu_series = ""
    for s in mcu_series:
        if s.endswith("x"):
            s = s[:-1]
        if mcu.startswith(s):
            detected_mcu_series = s
            break

    if not detected_mcu_series:
        print(f"cannot support mcu {args.mcu}")
        sys.exit()

    if args.firmware_path.endswith(".bin"):
        cmd = [
            openocd_bin,
            "-f",
            openocd_root + f"/scripts/interface/{tool}.cfg",
            "-f",
            openocd_root + f"/scripts/target/{detected_mcu_series}.cfg",
            "-c",
            f"program {args.firmware_path} exit {start}",
        ]
        print(shlex.join(cmd))
        if not args.dryrun:
            subprocess.run(cmd, check=True)
            pass
        return
    if args.firmware_path.endswith(".elf") or args.firmware_path.endswith(".hex"):
        cmd = [
            openocd_bin,
            "-f",
            openocd_root + f"/scripts/interface/{tool}.cfg",
            "-f",
            openocd_root + f"/scripts/target/{detected_mcu_series}.cfg",
            "-c",
            f"program {args.firmware_path} verify reset exit",
        ]
        print(shlex.join(cmd))
        if not args.dryrun:
            subprocess.run(cmd, check=True)
            pass
        return
    print(f"unknown firmware {args.firmware_path}")
    sys.exit(1)


def flash_mcu(args: Args):
    mcu = args.mcu.lower()
    if mcu.startswith("stm32"):
        flash_stm32(args)
        return

    print(f"mcu {mcu} is not supported")
    sys.exit(1)


def parse_args() -> Args:
    parser = argparse.ArgumentParser(
        prog="flash-mcu.py",
        description="openocd wrapper for PlatformIO user",
        epilog="Text at the bottom of help",
    )

    parser.add_argument("mcu", help="mcu name", type=str)
    parser.add_argument("firmware", help="firmware path (.bin/.elf/.hex)", type=str)
    parser.add_argument("-s", "--start", help="start address", type=str, required=False)
    parser.add_argument("-t", "--tool", help="flash tool", type=str, required=False)
    parser.add_argument("-d", "--dryrun", help="dry run", type=bool, required=False)

    args = parser.parse_args()

    return Args(
        mcu=args.mcu,
        firmware_path=args.firmware,
        start=args.start,
        tool=args.tool,
        dryrun=args.dryrun,
    )


def main():
    args = parse_args()

    if not os.path.exists(args.firmware_path):
        print(f"firmware {args.firmware_path} does not exist")
        sys.exit(1)

    flash_mcu(args)


if __name__ == "__main__":
    main()
