#!/bin/sh

set -eu

CPUS="0,2,4,6"
COUNTERS="mem_load_retired.l1_hit,mem_load_retired.l1_miss,mem_load_retired.l2_hit,mem_load_retired.l2_miss"

BENCHMARK="$1"
shift

mkdir -p "$BCPI_PMC_DIR/$BENCHMARK"
OUT="$(mktemp "$BCPI_PMC_DIR/$BENCHMARK/pmc.XXXXXXXXXX")"

echo "$@" >"$OUT"
cpuset -l "$CPUS" -- pmc stat -j "$COUNTERS" -- "$@" 2>>"$OUT"
