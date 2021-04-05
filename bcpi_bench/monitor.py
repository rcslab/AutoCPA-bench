#!/usr/bin/env python3

"""
Process spawning monitoring.
"""


from .config import Config

from contextlib import ExitStack
from datetime import datetime
import logging
import os
from pathlib import Path, PurePath
import shlex
import subprocess
import sys
from tempfile import NamedTemporaryFile, mkdtemp
from typing import List


class Monitor:
    """
    A process monitor.
    """

    def __init__(self, config: Config):
        self._stack = ExitStack()

        time = datetime.utcnow().isoformat(sep="/")
        self._dir = os.path.join(config.common.output_dir, "monitor_logs")
        os.makedirs(self._dir)

        self._verbose = config.common.monitor_verbose

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

    def _spawn(self, command, name, bg=False, check=True) -> subprocess.Popen:
        if self._verbose:
            logging.info(f"Monitor - spawning {command}. " + ("[bg]" if bg else "") + ("[chk]" if check else ""))

        if bg or not self._verbose:
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
            if check:
                self.check_success(proc)
            else:
                proc.wait()

        return proc

    def spawn(self, command, bg=False, check=True) -> subprocess.Popen:
        """
        Run a command.
        """

        name = PurePath(command[0]).name
        return self._spawn(command, name=name, bg=bg, check=check)

    def ssh_spawn(self, address, command, bg=False, check=True) -> subprocess.Popen:
        """
        Run a command over ssh.
        """

        cmd = ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-tt"]
        if not self._verbose:
            cmd.append("-q")
        cmd += [address, "--"]
        cmd += [shlex.quote(arg) for arg in command]

        name = PurePath(command[0]).name

        return self._spawn(cmd, name=f"{address}.{name}", bg=bg, check=check)

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
