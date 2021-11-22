#!/bin/sh

set -ue

SPEC_INST=$1

# Which benchmarks to run
BENCHSET=intrate_no_fortran

# Number of runs
ITERATIONS=3

# Concurrency for rate benchmarks
COPIES=4

if ! [ -d "$SPEC_INST/tools/bin/freebsd-x86_64" ]; then
    (
        cd "$SPEC_INST"
        tar xf install_archives/tools-src.tar
        BUILDTOOLS_KEEP_GOING=1 ./tools/src/buildtools
        packagetools freebsd-x86_64
    )
fi

rm -rf ./cpu2017-baseline ./cpu2017-patched

~/cpu2017-inst/install.sh -d "$PWD/cpu2017-baseline" -u freebsd-x86_64 -f
cp ./spec-bcpi.cfg ./cpu2017-baseline/config/

cp -r ./cpu2017-baseline ./cpu2017-patched
patch -s -p1 -d ./cpu2017-patched <./patches/spec.patch

spec-build() {
    (
        cd "$1"
        . ./shrc
        runcpu --config=spec-bcpi --action=build $BENCHSET
    )
}

save-result() {
    mkdir -p "${2%/*}"
    mv "$1/result" "$2"
}

spec-run() {
    ROOT="$PWD"

    for iter in $(seq $ITERATIONS); do
        printf "========\nIteration %d\n========\n\n" $iter

        (
            cd "$1"
            . ./shrc
            export BCPI_PMC_DIR="$ROOT/cpu2017-results/$1/base/$iter/pmc"
            runcpu --config=spec-bcpi --copies=$COPIES --iterations=1 --nobuild --tune=base $BENCHSET
        )
        save-result "$1" "./cpu2017-results/$1/base/$iter/result"

        (
            cd "$1"
            . ./shrc
            export BCPI_PMC_DIR="$ROOT/cpu2017-results/$1/peak/$iter/pmc"
            runcpu --config=spec-bcpi --copies=$COPIES --iterations=1 --nobuild --tune=peak $BENCHSET
        )
        save-result "$1" "./cpu2017-results/$1/peak/$iter/result"
    done
}

spec-build ./cpu2017-baseline
spec-build ./cpu2017-patched

spec-run ./cpu2017-baseline
spec-run ./cpu2017-patched
