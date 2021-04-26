#!/usr/bin/env python3

"""
Process spawning monitoring.
"""


from .config import Config

from contextlib import ExitStack
from pathlib import Path, PurePath
from tempfile import NamedTemporaryFile, mkdtemp
from typing import List

import logging
import shlex
import subprocess
import sys


class Monitor:
    """
    A process monitor.
    """

    def __init__(self, config: Config):
        self._stack = ExitStack()

        self._dir = Path(config.output_dir)/"monitor_logs"
        self._dir.mkdir(parents=True, exist_ok=True)

        self._verbose = config.verbose

    def __enter__(self):
        self._stack.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._stack.__exit__(exc_type, exc_value, traceback)

    def get_args(self, proc):
        return proc.args

    def check_running(self, proc) -> bool:
        return proc.poll() is None

    def wait(self, proc):
        proc.wait()

    def wait_all(self, procs):
        for proc in procs:
            self.wait(proc)

    def get_return_code(self, proc):
        return proc.returncode

    def check_success(self, proc):
        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"Process failed with status {proc.returncode}, args: {proc.args}")

    def check_success_all(self, procs):
        for proc in procs:
            self.check_success(proc)

    def _spawn(self, command, name, bg=False, check=True, stdout_override=None, stderr_override=None) -> subprocess.Popen:
        if self._verbose:
            logging.info(f"Monitor - spawning {command}. " + ("[bg]" if bg else "") + ("[chk]" if check else ""))

        if bg or not self._verbose:
            stdin = subprocess.DEVNULL
            # Don't create temp files if we are overriding
            command_str = ' '.join(map(str, command)) + "\n"
            if stdout_override == None:
                f = NamedTemporaryFile(prefix=f"{name}.", suffix=".stdout", dir=self._dir, delete=False)
                f.write(command_str.encode())
                stdout = f
            if stderr_override == None:
                f = NamedTemporaryFile(prefix=f"{name}.", suffix=".stderr", dir=self._dir, delete=False)
                f.write(command_str.encode())
                stderr = f
        else:
            stdin = None
            stdout = None
            stderr = None

        if stdout_override != None:
            stdout = stdout_override
        if stderr_override != None:
            stderr = stderr_override

        proc = subprocess.Popen(command, stdin=stdin, stdout=stdout, stderr=stderr)

        if bg:
            self._stack.enter_context(proc)
        else:
            if check:
                self.check_success(proc)
            else:
                proc.wait()

        return proc

    def spawn(self, command, bg=False, check=True, stdout_override=None, stderr_override=None) -> subprocess.Popen:
        """
        Run a command.
        """

        name = PurePath(command[0]).name
        return self._spawn(command, name=name, bg=bg, check=check, stdout_override=stdout_override, stderr_override=stderr_override)

    def ssh_spawn(self, address, command, bg=False, check=True, stdout_override=None, stderr_override=None) -> subprocess.Popen:
        """
        Run a command over ssh.
        """

        cmd = ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-tt"]
        if not self._verbose:
            cmd.append("-q")
        cmd += [address, "--"]
        cmd += [shlex.quote(arg) for arg in command]

        name = PurePath(command[0]).name

        return self._spawn(cmd, name=f"{address}.{name}", bg=bg, check=check, stdout_override=stdout_override, stderr_override=stderr_override)

    def ssh_spawn_all(self, addresses, command, bg=False, check=True) -> List[subprocess.Popen]:
        """
        Run ssh commands for all addresses, returning an array of procs
        """

        each_bg = bg
        if len(addresses) > 1:
            each_bg = True

        procs = []
        for addr in addresses:
            procs.append(self.ssh_spawn(addr, command, bg=each_bg, check=check))

        if not bg:
            if check:
                self.check_success_all(procs)
            else:
                self.wait_all(procs)

        return procs
