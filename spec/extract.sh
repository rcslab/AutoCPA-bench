#!/bin/sh

set -eu

SPEC_ISO="$1"
SPEC_DIR="$2"

if [ -d "$SPEC_DIR" ]; then
    echo "SPEC CPU 2017 already extracted to $SPEC_DIR"
else
    echo "Extracting SPEC CPU 2017 to $SPEC_DIR ..."
    mkdir -p "$SPEC_DIR"
    tar xf "$SPEC_ISO" -C "$SPEC_DIR"
    chmod -R u+w "$SPEC_DIR"
fi

UNAME=$(uname -s | tr '[A-Z]' '[a-z]')
MACHINE=$(uname -m | tr '[A-Z]' '[a-z]')
TOOLS="$UNAME-$MACHINE"
TOOLS_DIR="$SPEC_DIR/tools/bin/$TOOLS"

if [ -d "$TOOLS_DIR" ]; then
    echo "Tools already built at $TOOLS_DIR"
else
    echo "Building tools for $TOOLS ..."
    (
        cd "$SPEC_DIR"
        tar xf install_archives/tools-src.tar
        export SKIPTOOLSINTRO=1
        export BUILDTOOLS_KEEP_GOING=1
        export MAKEFLAGS="-j$(sysctl -n hw.ncpu)"
        export CFLAGS="-fcommon"
        export SPEC="$PWD"
        ./tools/src/buildtools
        ./bin/packagetools "$TOOLS"
    )
fi
