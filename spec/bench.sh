# Which benchmarks to run
BENCHSET=(intrate_no_fortran)

# Which tunings to use
TUNINGS=(base) #(base peak)

# Concurrency for rate benchmarks
COPIES=4

# Turn off the adjacent cache line prefetcher
acp-off() {
    model=$(sysctl -n hw.model)
    if [[ $model != *Xeon* ]]; then
        echo "Don't know how to turn off the adjacent cache line prefetcher on $model" >&2
        return 1
    fi

    for cpu in /dev/cpuctl*; do
        read _ _ high low < <(cpucontrol -m 0x1A4 "$cpu")
        if ((!(low & 0x2))); then
            cpucontrol -m "0x1A4|=0x2" "$cpu"
            at-exit cpucontrol -m "0x1A4&=~0x2" "$cpu"
        fi
    done
}

setup() {
    iso=
    install=0
    patch=0
    build=0

    local OPTIND opt
    while getopts 'x:ipb' opt; do
        case "$opt" in
            x)
                iso="$OPTARG"
                ;;
            i)
                install=1
                patch=1
                ;;
            p)
                patch=1
                ;;
            b)
                build=1
                ;;
            *)
                return 1
                ;;
        esac
    done

    if [ "$iso" ]; then
        as-user ./spec/extract.sh "$iso" ./cpu2017
    fi

    if ((install)); then
        as-user rm -rf ./cpu2017-baseline
        as-user ./spec/install.sh ./cpu2017 ./cpu2017-baseline
        as-user cp ./spec/bcpi.cfg ./cpu2017-baseline/config/
    fi

    if ((patch)); then
        as-user rm -rf ./cpu2017-patched
        as-user cp -r ./cpu2017-{baseline,patched}
        as-user patch -s -p1 -d ./cpu2017-patched <./patches/spec.patch
    fi

    if ((build)); then
        for tune in "${TUNINGS[@]}"; do
            for dir in cpu2017-{baseline,patched}; do
                as-user ./spec/run.sh "$dir" runcpu --config=bcpi --action=build --rebuild --tune="$tune" "${BENCHSET[@]}"
            done
        done
    fi

    kldload -n hwpmc
    kldload -n cpuctl

    acp-off

    max-freq
    aslr-off
}

bench() {
    for tune in "${TUNINGS[@]}"; do
        for dir in cpu2017-{baseline,patched}; do
            output="$BENCH_DIR/$dir/$tune"
            mkdir -p "$output"

            export BCPI_PMC_DIR="$(realpath -- "$output")/pmc"
            ./spec/run.sh "$dir" runcpu --config=bcpi --copies=$COPIES --iterations=1 --nobuild --tune="$tune" "${BENCHSET[@]}"
            mv "$dir/result" "$output/"
        done
    done
}
