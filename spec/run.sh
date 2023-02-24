#!/bin/sh

# Run a command in a SPEC CPU 2017 installation

set -eu

cd "$1"
shift

. ./shrc
"$@"

