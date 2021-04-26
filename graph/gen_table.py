import os
import click
import re
import numpy as np
from typing import Optional, List, Dict

class PMCParser():
    def get_property(self, name : str):
        if name in self._lookup:
            return self._lookup[name]
        return None

    def __init__(self, lines: List[str]):
        self._lookup = {}
        for line in lines:
            line = line.strip()
            if re.match(r"(\d+) +(.*)", line):
                line = line.replace("\t", " ")
                lines = re.split(r" +", line)
                if len(lines) >= 2:
                    self._lookup[lines[1]] = int(lines[0])


class Category():
    def get_property(self, name : str):
        if name in self._properties:
            return self._properties[name]
        return None

    def add_property(self, name : str, obj : list):
        self._properties[name] = obj

    def __init__(self, pmc_arr: List[PMCParser]):
        self._properties = {}
        for prop in properties:
            self._properties[prop] = []
            for parser in pmc_arr:
                if parser.get_property(prop) != None:
                    self._properties[prop].append(parser.get_property(prop))
    
        # handle extra props
        for prop_tup in extra_properties:
            prop_tup[1](self, prop_tup[0])

def extra_prop_ipc(cat : Category, name : str):
    ins_prop = cat.get_property("instructions")
    cyc_prop = cat.get_property("cycles")
    cat.add_property(name, [np.sum(ins_prop) / np.sum(cyc_prop)])

def extra_prop_l1_miss_rate(cat : Category, name : str):
    miss = cat.get_property("mem_load_retired.l1_miss")
    hit = cat.get_property("mem_load_retired.l1_hit")
    cat.add_property(name, [np.sum(miss) / (np.sum(miss) + np.sum(hit))])

def extra_prop_l2_miss_rate(cat : Category, name : str):
    miss = cat.get_property("mem_load_retired.l2_miss")
    hit = cat.get_property("mem_load_retired.l2_hit")
    cat.add_property(name, [np.sum(miss) / (np.sum(miss) + np.sum(hit))])

def extra_prop_l3_miss_rate(cat : Category, name : str):
    miss = cat.get_property("mem_load_retired.l3_miss")
    hit = cat.get_property("mem_load_retired.l3_hit")
    cat.add_property(name, [np.sum(miss) / (np.sum(miss) + np.sum(hit))])

extra_properties = [
    ("IPC", extra_prop_ipc),
    ("l1 miss rate", extra_prop_l1_miss_rate),
    ("l2 miss rate", extra_prop_l2_miss_rate),
    ("l3 miss rate", extra_prop_l3_miss_rate)
]

properties = [
    "cycles",
    "instructions",
    "mem_load_retired.l3_hit",
    "mem_load_retired.l3_miss",
    "mem_load_retired.l2_hit",
    "mem_load_retired.l2_miss",
    "mem_load_retired.l1_hit",
    "mem_load_retired.l1_miss"
]

def mad(arr: list):
    sum = 0
    mean = np.mean(arr)
    for i in arr:
        sum = sum + np.abs(i - mean)
    return sum / len(arr)

def process_subdirectory(path : str, out : List[PMCParser]):
    for filename in os.listdir(path):
        realpath = os.path.join(path, filename)
        if os.path.isdir(realpath):
            process_subdirectory(realpath, out)
        
        if not (("pmc" in filename) and ("stdout" in filename)):
            continue

        print(f"Processing {realpath}...")

        with open(realpath, "r") as f:
            lines = f.readlines()
            out.append(PMCParser(lines))

def get_category_baseline(name : str):
    idx = name.rfind("_")
    name = name[:idx]
    name += "_baseline"
    return name


def print_arr(name : str, arr : list, baseline : list):
    mean = np.mean(arr)
    mean_b = np.mean(baseline)
    diff = (mean - mean_b) / mean_b * 100
    madd = mad(arr)
    print(name.ljust(30) + 
        ("%.4f" % mean).ljust(20) + 
        (("%.4f" % diff) if diff < 0 else ('+' + "%.4f" % diff)).ljust(15) + 
        str(len(arr)).ljust(10) + 
        ("%.4f" % madd).ljust(20) +
        ("%.4f" % (madd / mean * 100)).ljust(10))


def print_category(category_list : List[Category], category_map : dict):
    category_list.sort()
    print("\n")
    for cat in category_list:
        cat_obj = category_map[cat]

        baseline_name = get_category_baseline(cat)
        if baseline_name in category_map:
            baseline_obj = category_map[baseline_name]
        else:
            baseline_obj = cat_obj
            baseline_name = cat

        print(f"Category: {cat}    Baseline: {baseline_name}")
        print(''.ljust(30) + 
            'Mean'.ljust(20) +
            'Baseline%'.ljust(15) +
            'Count'.ljust(10) + 
            'MAD'.ljust(20) + 
            'MAD%'.ljust(10))
        
        for prop in properties:
            prop_data = cat_obj.get_property(prop)
            baseline_data = baseline_obj.get_property(prop)
            print_arr(prop, prop_data, baseline_data)

        for prop in extra_properties:
            prop_data = cat_obj.get_property(prop[0])
            baseline_data = baseline_obj.get_property(prop[0])
            print_arr(prop[0], prop_data, baseline_data)

        print("\n")

def process_directory(path : str):
    category_map = {}
    category_list = []
    for filename in os.listdir(path):
        realpath = os.path.join(path, filename)
        print(f"Found category {filename}")
        output = []
        process_subdirectory(realpath, output)
        category_map[filename] = Category(output)
        category_list.append(filename)
    
    print_category(category_list, category_map)
    

@click.command()
@click.argument("path", type=str)
def cli(path):
    process_directory(path)

if __name__ == '__main__':
    cli()