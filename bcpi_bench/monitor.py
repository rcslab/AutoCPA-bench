#!/usr/bin/env python3

"""
Process spawning monitoring.
"""

from contextlib import ExitStack
from datetime import datetime
from pathlib import Path, PurePath
from shlex import quote
import subprocess
from tempfile import NamedTemporaryFile, mkdtemp


class Monitor:
    """
    A process monitor.
    """

    def __init__(self):
        self._stack = ExitStack()

        time = datetime.utcnow().isoformat(sep="/")
        self._dir = Path(f"logs/{time}")
        self._dir.mkdir(parents=True)

    def __enter__(self):
        self._stack.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._stack.__exit__(exc_type, exc_value, traceback)

    def _check_success(self, proc):
        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"Process failed with status {proc.returncode}")

    def _spawn(self, command, name, bg=False, check=True) -> subprocess.Popen:
        if bg:
            stdin = subprocess.DEVNULL
            stdout = NamedTemporaryFile(prefix=f"{name}.", suffix=".stdout", dir=self._dir, delete=False)
            stderr = NamedTemporaryFile(prefix=f"{name}.", suffix=".stderr", dir=self._dir, delete=False)
        else:
            stdin = None
            stdout = None
            stderr = None

        proc = subprocess.Popen(command, stdin=stdin, stdout=stdout, stderr=stderr)
        proc.stdout = stdout
        proc.stderr = stderr

        if bg:
            self._stack.enter_context(proc)
        else:
            proc.wait()
            if check:
                self._check_success(proc)

        return proc

    def spawn(self, command, bg=False, check=True) -> subprocess.Popen:
        """
        Run a command.
        """

        name = PurePath(command[0]).name
        self._spawn(command, name=name, bg=bg, check=check)

    def ssh_spawn(self, address, command, bg=False, check=True) -> subprocess.Popen:
        """
        Run a command over ssh.
        """

        cmd = ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-ttq", address, "--"]
        cmd += [quote(arg) for arg in command]
        name = PurePath(command[0]).name
        return self._spawn(cmd, name=f"{address}.{name}", bg=bg, check=check)
