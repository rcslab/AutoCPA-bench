#!/usr/bin/env python3

"""
Process spawning monitoring.
"""
import sys
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path, PurePath
from .config import Config
from .parser import *
import subprocess
import logging
from tempfile import NamedTemporaryFile, mkdtemp


class Monitor:
    """
    A process monitor.
    """

    def __init__(self, config: Config):
        self._stack = ExitStack()

        time = datetime.utcnow().isoformat(sep="/")
        self._dir = Path(f"logs/{time}")
        self._dir.mkdir(parents=True)
        self.config = config.common

    def _get_verbose(self) -> bool:
        return self.config.monitor_verbose != 0

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
        if self._get_verbose():
            logging.info(f"Monitor - spawning {command}. " + ("[bg]" if bg else "") + ("[chk]" if check else ""))

        if bg:
            stdin = subprocess.DEVNULL
            stdout = NamedTemporaryFile(prefix=f"{name}.", suffix=".stdout", dir=self.config.output_dir, delete=False)
            stderr = NamedTemporaryFile(prefix=f"{name}.", suffix=".stderr", dir=self.config.output_dir, delete=False)
        else:
            stdin = None
            if self._get_verbose():
                stdout = sys.stdout
                stderr = sys.stderr
            else:
                stdout = subprocess.PIPE
                stderr = subprocess.PIPE

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
        if not self._get_verbose():
            cmd.append("-q")
        cmd.extend([address, "--"])
        cmd.extend(command)
        name = PurePath(command[0]).name
        return self._spawn(cmd, name=f"{address}.{name}", bg=bg, check=check)

    def ssh_spawn_all(self, addresses, command, bg=False, check=True) -> [subprocess.Popen]:
        """
        Run ssh commands for all addresses, returning an array of procs
        """

        proc = []
        for addr in addresses:
            proc.append(self.ssh_spawn(addr, command, bg=bg, check=check))
        return proc