#!/bin/sh

set -eu

SPEC_DIR=$(realpath -- "$1")

mkdir "$2"
SPEC_TARGET=$(realpath -- "$2")

(
    # The Perl test op/magic.t fails due to hardcoding "perl" rather than
    # "specperl", but we can skip it by making ps fail
    TMP=$(mktemp -d)
    ln -s "$(which false)" "$TMP/ps"
    export PATH="$TMP:$PATH"
    "$SPEC_DIR/install.sh" -d "$SPEC_TARGET" -f
    rm -r "$TMP"
)
