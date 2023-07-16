#!env python3
from pathlib import Path
import shlex
import subprocess
import sys
import argparse
from typing import Optional, Sequence, Union

from dataclasses import dataclass

CMD = Sequence[Union[str, Path]]


class NotFoundException(Exception):
    pass


def print_cmd(cmd: CMD):
    print(shlex.join(str(c) for c in cmd))


def which(exe: str) -> Path:
    p = subprocess.run(["which", exe], capture_output=True, text=True)
    if p.returncode == 0:
        return Path(p.stdout.strip())
    raise NotFoundException(f"cannot found {exe}")


@dataclass
class Args:
    mcu: str
    firmware_path: str
    tool: Optional[str]
    port: Optional[str]
    start: Optional[str]
    dryrun: bool


def get_platformio_package_path(package: str) -> Path:
    package_path = Path("~", ".platformiopackages", package).expanduser()
    if not package_path.exists():
        raise NotFoundException(f"platform package {package} not found")
    return package_path


def get_platformio_package_bin_path(package: str, executable: str) -> Path:
    package_path = get_platformio_package_path(package)
    bin_path = package_path.joinpath("bin", executable)
    if not bin_path.exists():
        raise NotFoundException(
            f"PlatformIO package {package} does not have {executable}"
        )
    return bin_path


def detect_openocd_path() -> tuple[Path, Path]:
    if (
        Path("/usr/local/bin/openocd").exists()
        and Path("/usr/local/share/openocd").exists()
    ):
        return Path("/usr/local/bin/openocd"), Path("/usr/local/share/openocd")

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
    for series in mcu_series:
        if series.endswith("x"):
            series_start = series[:-1]
        else:
            series_start = series
        if mcu.startswith(series_start):
            detected_mcu_series = series
            break

    if not detected_mcu_series:
        print(f"cannot support mcu {args.mcu}")
        sys.exit()

    print(detected_mcu_series)
    if args.firmware_path.endswith(".bin"):
        cmd: Sequence[Union[str, Path]] = [
            openocd_bin,
            "-f",
            openocd_root.joinpath("scripts", "interface", f"{tool}.cfg"),
            "-f",
            openocd_root.joinpath("scripts", "target", f"{detected_mcu_series}.cfg"),
            "-c",
            f"program {args.firmware_path} exit {start}",
        ]
        print(shlex.join(str(c) for c in cmd))
        if not args.dryrun:
            subprocess.run(cmd, check=True)
            pass
        return
    if args.firmware_path.endswith(".elf") or args.firmware_path.endswith(".hex"):
        cmd = [
            openocd_bin,
            "-f",
            openocd_root.joinpath("scripts", "interface", f"{tool}.cfg"),
            "-f",
            openocd_root.joinpath("scripts", "target", f"{detected_mcu_series}.cfg"),
            "-c",
            f"program {args.firmware_path} verify reset exit",
        ]
        print(shlex.join(str(c) for c in cmd))
        if not args.dryrun:
            subprocess.run(cmd, check=True)
            pass
        return
    print(f"unknown firmware {args.firmware_path}")
    sys.exit(1)


def detect_esptool_path() -> list[Path]:
    if Path("~/.platformio/packages/tool-esptoolpy").expanduser().exists():
        python_path = Path("~/.platformio/penv/bin/python").expanduser()
        tool_path = Path(
            "~/.platformio/packages/tool-esptoolpy/esptool.py"
        ).expanduser()
        return [python_path, tool_path]
    tool_path = which("esptool.py")
    return [tool_path]


def flash_esp32(args: Args):
    if args.port is None:
        print("need port: --port /dev/ttyACM0")
        sys.exit(1)
    if not Path(args.port).exists():
        raise NotFoundException(f"port {args.port} does not found")
    esptool_cmd = detect_esptool_path()
    cmd = esptool_cmd + [
        f"--chip={args.mcu}",
        f"--port={args.port}",
        "write_flash",
        # "--flash_freq=20m",
        "--flash_size=detect",
        "0",
        args.firmware_path,
    ]
    print_cmd(cmd)

    if not args.dryrun:
        subprocess.run(cmd, check=True)
        pass
    return


def flash_mcu(args: Args):
    mcu = args.mcu.lower()
    if mcu.startswith("stm32"):
        flash_stm32(args)
        return
    if mcu.startswith("esp32"):
        flash_esp32(args)
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
    parser.add_argument("-p", "--port", help="port", type=str, required=False)
    parser.add_argument("-d", "--dryrun", help="dry run", action='store_true')

    args = parser.parse_args()

    return Args(
        mcu=args.mcu,
        firmware_path=args.firmware,
        start=args.start,
        tool=args.tool,
        port=args.port,
        dryrun=args.dryrun,
    )


def main():
    args = parse_args()

    if not Path(args.firmware_path).exists():
        print(f"firmware {args.firmware_path} does not exist")
        sys.exit(1)

    try:
        flash_mcu(args)
    except NotFoundException as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
