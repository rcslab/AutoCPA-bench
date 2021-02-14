#!/usr/bin/env python3

import logging
import os
from pathlib import Path
import subprocess
import sys
import venv


PARENT_DIR = Path(__file__).resolve().parent


def bootstrap():
    """
    Set up the local environment for cluster.py.
    """

    venv_dir = PARENT_DIR / "venv"
    venv_exec = PARENT_DIR / "venv-exec.sh"
    requirements = PARENT_DIR / "requirements.txt"

    if not venv_dir.is_dir():
        logging.warning("Virtual environment does not exist, creating")
        venv.create(venv_dir, symlinks=True, with_pip=True)
        subprocess.run([venv_exec, venv_dir, "pip", "install", "--upgrade", "pip"]).check_returncode()
        subprocess.run([venv_exec, venv_dir, "pip", "install", "-r", requirements]).check_returncode()

    if "VIRTUAL_ENV" not in os.environ:
        logging.info("Activating virtual environment")
        os.execl(venv_exec, venv_exec, venv_dir, *sys.argv)


def main():
    bootstrap()

    from bcpi_bench.__main__ import cli
    cli.main()


if __name__ == "__main__":
    main()
