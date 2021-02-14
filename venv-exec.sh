#!/bin/sh

# Run a command inside a virtual environment

venv="$1"
shift
. "$venv/bin/activate"
"$@"
