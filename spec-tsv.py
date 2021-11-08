#!/usr/bin/env python3

from collections import defaultdict
import csv
import numpy as np
from pathlib import Path
import sys


COUNTERS = {
    "cycles",
    "instructions",
    "mem_load_retired.l1_hit",
    "mem_load_retired.l1_miss",
    "mem_load_retired.l2_hit",
    "mem_load_retired.l2_miss",
    "mem_load_retired.l3_hit",
    "mem_load_retired.l3_miss",
}


def fill_times(data, paths):
    for path in paths:
        with open(path, "r", newline="") as f:
            reader = csv.reader(f)
            for row in reader:
                if row and row[-1] == "refrate(ref) iteration #1":
                    part = data.setdefault(row[0], defaultdict(list))
                    times = part["time"]
                    time = row[2] or row[7]
                    if time:
                        times.append(float(time))


def fill_pmc(data, paths):
    partial = defaultdict(list)

    for path in paths:
        with open(path, "r", newline="") as f:
            for line in f.readlines():
                chunks = line.split()
                if len(chunks) < 2:
                    continue
                counter = chunks[1]
                if counter in COUNTERS:
                    partial[counter].append(int(chunks[0]))

    for counter, values in partial.items():
        data[counter].append(sum(values))


DATA = {
    "base": {
        "baseline": {},
        "patched": {},
    },
    "peak": {
        "baseline": {},
        "patched": {},
    },
}

results = Path(sys.argv[1])
benchmarks = set()

for tune in DATA.keys():
    for exp in DATA[tune].keys():
        part = DATA[tune][exp]

        path = results/f"cpu2017-{exp}"/tune
        fill_times(part, path.glob("*/result/*.csv"))

        for benchmark in part.keys():
            benchmarks.add(benchmark)
            for run in path.glob("*/"):
                fill_pmc(part[benchmark], run.glob(f"pmc/{benchmark}/*.err"))


MEDIANS = [
    ["", "Before"] + ([""] * 9) + ["After"] + ([""] * 9),
    [""] + (["Base"] + ([""] * 4) + ["Peak"] + ([""] * 4)) * 2,
    [""] + (["Time", "IPC", "L1 miss rate", "L2 miss rate", "L3 miss rate"] * 4),
]

VARIANCES = [
    [],
    ["", "Variance (PTP)"],
]

for benchmark in sorted(benchmarks):
    median = [benchmark]
    variance = [benchmark]

    for exp in ["baseline", "patched"]:
        for tune in ["base", "peak"]:
            part = DATA[tune][exp][benchmark]

            time = part["time"]
            if time:
                median.append(np.median(time))
                variance.append(np.ptp(time))
            else:
                median.append("")
                variance.append("")

            insts = np.array(part["instructions"])
            cycles = np.array(part["cycles"])
            ipc = insts / cycles
            if len(ipc):
                median.append(np.median(ipc))
                variance.append(np.ptp(ipc))
            else:
                median.append("")
                variance.append("")

            for level in range(1, 4):
                hit = np.array(part[f"mem_load_retired.l{level}_hit"])
                miss = np.array(part[f"mem_load_retired.l{level}_miss"])
                rate = miss / (hit + miss)
                if len(rate):
                    median.append(np.median(rate))
                    variance.append(np.ptp(rate))
                else:
                    median.append("")
                    variance.append("")

    MEDIANS.append(median)
    VARIANCES.append(variance)

writer = csv.writer(sys.stdout, delimiter='\t')
writer.writerows(MEDIANS + VARIANCES)
