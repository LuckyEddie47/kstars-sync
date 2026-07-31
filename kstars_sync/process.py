"""
process.py

Process-related utilities for kstars-sync.

This module owns all application process handling:

- Detecting whether an executable is already running.
- Launching an application.
- Waiting for it to exit.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import subprocess
import os
import psutil


class ProcessError(Exception):
    """Raised when process inspection or execution fails."""


@dataclass(slots=True)
class ProcessInfo:
    """Information about a running process."""

    pid: int
    name: str
    executable: Optional[Path]
    command_line: list[str]


@dataclass(slots=True)
class CompletedApplication:
    """Result of running an application."""

    returncode: int


def find_process(executable: str | Path) -> Optional[ProcessInfo]:
    """
    Locate a running process by executable path.

    Parameters
    ----------
    executable
        Path to the executable to search for.

    Returns
    -------
    ProcessInfo if a matching process is found, otherwise None.
    """

    target = Path(executable).resolve()

    try:
        for proc in psutil.process_iter(
            ["pid", "name", "exe", "cmdline"]
        ):
            try:
                exe = proc.info["exe"]

                if exe is None:
                    continue

                exe_path = Path(exe).resolve()

                if exe_path != target:
                    continue

                cmdline = proc.info.get("cmdline") or []

                return ProcessInfo(
                    pid=proc.info["pid"],
                    name=proc.info["name"] or "",
                    executable=exe_path,
                    command_line=list(cmdline),
                )

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                FileNotFoundError,
            ):
                continue

    except Exception as ex:
        raise ProcessError(str(ex)) from ex

    return None


def is_running(executable_path: Path | str) -> bool:
    """
    Check if an application matching the executable path or name is currently running.
    """
    path_obj = Path(executable_path)
    resolved_target = path_obj.resolve()
    target_name = path_obj.name.lower()
    current_pid = os.getpid()

    for proc in psutil.process_iter(["pid", "name", "exe", "cmdline", "status"]):
        try:
            if proc.info["pid"] == current_pid:
                continue
            if proc.info.get("status") == psutil.STATUS_ZOMBIE:
                continue

            # 1. Match exact resolved executable path
            proc_exe = proc.info.get("exe")
            if proc_exe and Path(proc_exe).resolve() == resolved_target:
                return True

            # 2. Match process name
            proc_name = proc.info.get("name") or ""
            if proc_name.lower() == target_name:
                return True

            # 3. Match executable name in cmdline
            cmdline = proc.info.get("cmdline") or []
            if any(target_name == Path(arg).name.lower() for arg in cmdline if arg):
                return True

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return False

def run_application(executable: str | Path) -> CompletedApplication:
    """
    Launch an application and wait for it to exit.

    Parameters
    ----------
    executable
        Executable to launch.

    Returns
    -------
    CompletedApplication

    Raises
    ------
    ProcessError
        If the application could not be started.
    """

    executable = Path(executable).resolve()

    try:
        process = subprocess.Popen(
            [str(executable)]
        )

    except OSError as ex:
        raise ProcessError(
            f"Failed to start '{executable}': {ex}"
        ) from ex

    try:
        return CompletedApplication(
            returncode=process.wait()
        )

    except Exception as ex:
        try:
            process.kill()
            process.wait(timeout=5)
        except Exception:
            pass

        raise ProcessError(
            f"Error waiting for '{executable}' to exit: {ex}"
        ) from ex