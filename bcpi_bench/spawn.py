#!/usr/bin/env python3

"""
Process spawning.
"""

import subprocess
from tempfile import TemporaryFile


def _check_success(proc):
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"Process failed with status {proc.returncode}")


def spawn(command, bg=False, check=True) -> subprocess.Popen:
    """
    Run a command.
    """

    if bg:
        stdin = subprocess.DEVNULL
        stdout = TemporaryFile(prefix="stdout")
        stderr = TemporaryFile(prefix="stderr")
    else:
        stdin = None
        stdout = None
        stderr = None

    proc = subprocess.Popen(command, stdin=stdin, stdout=stdout, stderr=stderr)
    proc.stdout = stdout
    proc.stderr = stderr

    if not bg:
        proc.wait()
        if check:
            _check_success(proc)

    return proc


def ssh_spawn(address, command, bg=False, check=True) -> subprocess.Popen:
    """
    Run a command over ssh.
    """

    cmd = ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-ttq", address, "--"] + list(command)
    return spawn(cmd, bg=bg, check=check)
