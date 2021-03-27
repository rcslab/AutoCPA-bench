#!/usr/bin/env python3

from .config import Config
from .monitor import Monitor
from .parser import *

import subprocess
import click
import logging
import datetime
import time
import sys
import os
import datetime

from pathlib import Path
from time import sleep


ROOT_DIR = Path(__file__).resolve().parent.parent

@click.group()
@click.option(
    "-c", "--conf",
    default=ROOT_DIR/"cluster.conf",
    type=click.File("r"),
    help="configuration file"
)
@click.option("-l", "--log", default="INFO", type=str, help="log level")
@click.pass_context
def cli(ctx, conf, log):
    """
    Control the BCPI benchmarking cluster.
    """

    ctx.obj = Config.load(conf)
    ctx.obj.common.output_dir = str(os.path.abspath(os.path.expanduser(os.path.join(ctx.obj.common.local_dir, datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))))
    os.makedirs(ctx.obj.common.output_dir, exist_ok=True)

    logging.basicConfig(level=getattr(logging, log.upper()))
    logging.getLogger().addHandler(logging.FileHandler(os.path.join(ctx.obj.common.output_dir, "log.txt")))


@cli.command()
@click.argument('servers', nargs=-1)
@click.pass_context
def ssh_copy_id(ctx, servers):
    """
    Install your public key on the given servers (default: all).
    """

    if not servers:
        servers = list(ctx.obj.servers.keys())

    with Monitor(ctx.obj) as monitor:
        for server in servers:
            address = ctx.obj.address(server)
            monitor.spawn(["ssh-copy-id", address])


@cli.command()
@click.argument('server', nargs=1)
@click.argument('command', nargs=-1)
@click.pass_context
def exec(ctx, server, command):
    """
    Execute a command on a server.
    """

    with Monitor(ctx.obj) as monitor:
        address = ctx.obj.address(server)
        monitor.ssh_spawn(address, command)

def _sync_build(monitor, server, remote_dir, targets, sync=True, build=True, clean=False):
    """
    Sync and build the code on a server.
    """

    if sync:
        logging.info(f"Syncing code to server {server}")
        monitor.ssh_spawn(server, ["mkdir", "-p", remote_dir])
        monitor.spawn(["rsync", "-aq", f"{ROOT_DIR}/.", f"{server}:{remote_dir}"])

    if clean:
        monitor.ssh_spawn(server, ["make", "-C", f"{remote_dir}"] + list("clean-" + t for t in targets))

    if build:
        logging.info(f"Building code on {server}")
        monitor.ssh_spawn(server, ["make", "-C", f"{remote_dir}", "-j48"] + list(targets))

@cli.command()
@click.option("--sync/--no-sync", default=True, help="Sync the code to the server (Default true)")
@click.option("--build/--no-build", default=True, help="Build the code to the server (Default true)")
@click.option("--clean/--no-clean", default=False, help="Clean the code to the server (Default false)")
@click.option('--server', default=None, help="Overwrite the default server list (Default conf.pkg.servers)")
@click.argument('targets', nargs=-1)
@click.pass_context
def build(ctx, sync, build, clean, server, targets):
    """
    Build the code on a server. Default targets: all
    """

    conf = ctx.obj

    remote_dir = conf.common.remote_dir

    if len(targets) == 0:
        targets = []
        targets.append("all")

    full_addresses = []
    if server != None:
        full_addresses.append(conf.address(server))
    else:
        for each in conf.pkg.servers:
            full_addresses.append(conf.address(each))

    procs = []
    with Monitor(conf) as monitor:
        if sync:
            logging.info(f"Syncing code...")
            procs.extend(monitor.ssh_spawn_all(full_addresses, ["mkdir", "-p", remote_dir], bg=True, check=False))
            monitor.check_success_all(procs)
            procs.clear()

            for addr in full_addresses:
                procs.append(monitor.spawn(["rsync", "-aq", f"{ROOT_DIR}/.", f"{addr}:{remote_dir}"], bg=True, check=False))
            monitor.check_success_all(procs)
            procs.clear()

        if clean:
            logging.info(f"Cleaning...")
            procs.extend(monitor.ssh_spawn_all(full_addresses, ["make", "-C", f"{remote_dir}"] + list("clean-" + t for t in targets), bg=True, check=False))
            monitor.check_success_all(procs)
            procs.clear()

        if build:
            logging.info(f"Building...")
            procs.extend(monitor.ssh_spawn_all(full_addresses, ["make", "-C", f"{remote_dir}", "-j12"] + list(targets), bg=True, check=False))
            monitor.check_success_all(procs)

@cli.command()
@click.pass_context
def rocksdb(ctx, **kwargs):
    conf = ctx.obj.rocksdb
    common_conf = ctx.obj.common
    bcpid_stub(ctx, _rocksdb, ctx.obj.address(conf.server),
                os.path.join(common_conf.remote_dir,"kqsched/pingpong/build/ppd"),**kwargs)

def _rocksdb(ctx, monitor):
    """
    Run the rocksdb benchmark.
    """
    success = False
    conf = ctx.obj
    rdb_conf = conf.rocksdb
    common_conf = conf.common
    sample_output = os.path.join(common_conf.remote_dir, "kqsched/pingpong/build/sample.txt")
    local_sample = f"{common_conf.output_dir}/rocksdb_sample.txt"

    server = conf.address(rdb_conf.server)
    master = conf.address(rdb_conf.master)
    ppd_exe = os.path.join(common_conf.remote_dir,"kqsched/pingpong/build/ppd")
    dismember_exe = os.path.join(common_conf.remote_dir,"kqsched/pingpong/build/dismember")
    affinity = int(rdb_conf.affinity) != 0
    full_addresses = [server, master]
    for client in rdb_conf.clients:
        full_addresses.append(conf.address(client))

    _rocksdb_killall(monitor, full_addresses)

    # start server
    ppd_cmd = ["sudo", ppd_exe, "-M", "2",
            "-O", f"PATH={rdb_conf.db_directory}", 
            "-t", str(rdb_conf.server_threads)]
    if affinity:
        ppd_cmd.extend(["-a"])
    
    logging.info(f"Starting server...")
    proc_ppd = monitor.ssh_spawn(server, ppd_cmd, bg=True)

    # start clients
    procs_client = []
    client_cmd = [dismember_exe, "-A"]
    logging.info(f"Starting clients...")
    for client in rdb_conf.clients:
        procs_client.append(monitor.ssh_spawn(conf.address(client), client_cmd, bg=True))

    time.sleep(3)
    # start master
    master_cmd = [dismember_exe, "-s", server,
                                "-q", str(rdb_conf.qps),
                                "-t", str(rdb_conf.client_threads),
                                "-c", str(rdb_conf.connections_per_thread),
                                "-W", str(rdb_conf.warmup),
                                "-w", str(rdb_conf.duration),
                                "-l", "2",
                                "-C", str(rdb_conf.master_connections),
                                "-T", str(rdb_conf.master_threads),
                                "-Q", str(rdb_conf.master_qps),
                                "-o", sample_output]
    for client in rdb_conf.clients:
        master_cmd.extend(["-a", conf.address(client)])
    logging.info(f"Starting master on {rdb_conf.master}...")
    proc_master = monitor.ssh_spawn(master, master_cmd, bg=True)

    # wait for master exit and in the meantime check if error has happened
    all_procs = [proc_master, proc_ppd]
    all_procs.extend(procs_client)

    elapsed_time = 0
    while elapsed_time <= ((rdb_conf.warmup + rdb_conf.duration) + 15):
        # check error
        err_proc = _rocksdb_checkerr(monitor, all_procs)
        if err_proc != None:
            logging.warn(f"Proc exited with code {monitor.get_return_code(err_proc)}, commandline {monitor.get_args(err_proc)}.")
            break

        # check master exited with 0
        if not monitor.check_running(proc_master):
            if monitor.get_return_code(proc_master) == 0:
                success = True
                break
        
        time.sleep(1)
        elapsed_time += 1

    # killall remaining processes
    _rocksdb_killall(monitor, full_addresses)

    if success:
        # scp back sample.txt
        scp_cmd = ["scp", f"{master}:{sample_output}", local_sample]
        monitor.spawn(scp_cmd, check=True)
        
        with open(local_sample, "r") as f:
            # parse results
            parsed = DismemberParser(f.readlines())
            logging.info(f"\n{MutilateParser.build_stdout(parsed.lat, parsed.qps)}")
    return success

def _rocksdb_killall(mon : Monitor, targets):
    for target in targets:
        mon.ssh_spawn(target, ["sudo", "killall", "ppd", "&&",
                               "sudo", "killall", "dismember"], check=False)

def _rocksdb_checkerr(mon : Monitor, targets) -> subprocess.Popen:
    for target in targets:
        if (not mon.check_running(target)) and (mon.get_return_code(target) != 0):
            return target
    return None

@cli.command()
@click.option("--server", default=None, help="Override the default server list with the server specified (conf lookup value)")
@click.option("--upgrade/--no-upgrade", default=False, help="Upgrade all packages (Default FALSE)")
@click.pass_context
def pkg(ctx, server, upgrade):
    """
    Install required pkgs on servers
    """
    conf = ctx.obj
    pkg_conf = conf.pkg

    full_addresses = []
    if server != None:
        full_addresses.append(conf.address(server))
    else:
        servers = pkg_conf.servers
        for each in servers:
            full_addresses.append(conf.address(each))
    
    procs = []
    cmd = ["sudo", "pkg", "update"]
    if upgrade:
        cmd += ["&&", "sudo", "pkg", "upgrade", "-y"]
    cmd += ["&&","sudo", "pkg", "remove", "-y"] + list(pkg_conf.pkg_rm) + ["||", "true"]
    cmd += ["&&", "sudo", "pkg", "install", "-y"] + list(pkg_conf.pkg)
    with Monitor(conf) as mon:
        procs = mon.ssh_spawn_all(full_addresses, cmd, bg=True, check=False)
        mon.check_success_all(procs)


@cli.command()
@click.option("--sync/--no-sync", default=True, help="ONLY Sync the code to the servers")
@click.option("--build/--no-build", default=True, help="ONLY Build the code on the servers")
@click.option("--pmc-stat/--no-pmc-stat", default=False, help="ONLY Run the benchmark under pmc stat")
@click.pass_context
def memcached(ctx, sync, build, pmc_stat):
    """
    Run the memcached benchmark.
    """

    conf = ctx.obj
    server = conf.address(conf.memcached.server)
    memcached_exe = os.path.join(conf.common.remote_dir, "memcached/memcached")
    mutilate_exe = os.path.join(conf.common.remote_dir, "mutilate/mutilate")

    with Monitor(conf) as monitor:
        full_addresses = []
        for client in conf.memcached.clients:
            full_addresses.append(conf.address(client))
        full_addresses.append(conf.address(conf.memcached.server))
        full_addresses.append(conf.address(conf.memcached.master))
        for addr in full_addresses:
            _sync_build(monitor, addr, conf.common.remote_dir, ["memcached", "mutilate"], sync=sync, build=build)
        if sync or build:
            return True

        logging.info(f"Starting memcached on {server}")
        server_cmd = [
            memcached_exe,
            "-m", "1024",
            "-c", "65536",
            "-b", "4096",
            "-t", str(conf.memcached.server_threads),
        ]
        if pmc_stat:
            server_cmd = ["pmc", "stat", "--"] + server_cmd
        server_proc = monitor.ssh_spawn(server, server_cmd, bg=True)

        sleep(1)
        logging.info(f"Pre-loading data on {server}")
        monitor.ssh_spawn(server, [mutilate_exe, "--loadonly", "-s", "localhost"])

        master_cmd = [
            mutilate_exe,
            "--noload",
            "-K", "fb_key",
            "-V", "fb_value",
            "-i", "fb_ia",
            "-u", "0.03",
            "-Q", "1000",
            "-T", str(conf.memcached.client_threads),
            "-C", "1",
            "-c", str(conf.memcached.connections_per_thread),
            "-w", str(conf.memcached.warmup),
            "-t", str(conf.memcached.duration),
            "-s", server,
        ]

        client_cmd = [
            mutilate_exe,
            "-A",
            "-T", str(conf.memcached.client_threads),
        ]
        clients = []
        for client in conf.memcached.clients:
            client_addr = conf.address(client)
            logging.info(f"Starting client on {client_addr}")
            clients.append(monitor.ssh_spawn(client_addr, client_cmd, bg=True))
            master_cmd += ["-a", client_addr]

        sleep(1)
        master = conf.address(conf.memcached.master)
        logging.info(f"Starting master on {master}")
        monitor.ssh_spawn(master, master_cmd)

        for client, proc in zip(conf.memcached.clients, clients):
            logging.info(f"Terminating client on {conf.address(client)}")
            proc.terminate()

        logging.info(f"Terminating server on {server}")
        monitor.ssh_spawn(server, ["killall", "memcached"])


@cli.command()
@click.option("--sync/--no-sync", default=True, help="Sync the code to the servers")
@click.option("--build/--no-build", default=True, help="Build the code on the servers")
@click.option("--pmc-stat/--no-pmc-stat", default=False, help="Run the benchmark under pmc stat")
@click.pass_context
def nginx(ctx, sync, build, pmc_stat):
    """
    Run the nginx benchmark.
    """

    conf = ctx.obj
    server = conf.address(conf.nginx.server)

    with Monitor(conf) as monitor:
        _sync_build(monitor, server, conf.common.remote_dir, ["nginx"], sync=sync, build=build)

        # Set up the nginx working directory
        logging.info(f"Starting nginx on {server}")
        monitor.ssh_spawn(server, ["rm", "-rf", conf.nginx.prefix])
        monitor.ssh_spawn(server, ["mkdir", "-p", conf.nginx.prefix + "/conf", conf.nginx.prefix + "/logs"])
        monitor.ssh_spawn(server, ["cp", "./bcpi-bench/" + conf.nginx.config, conf.nginx.prefix + "/conf"])
        monitor.ssh_spawn(server, ["cp", "./bcpi-bench/nginx/docs/html/index.html", conf.nginx.prefix])

        server_cmd = [
            "./bcpi-bench/nginx/objs/nginx",
            "-e", "stderr",
            "-p", conf.nginx.prefix,
        ]
        if pmc_stat:
            server_cmd = ["pmc", "stat", "--"] + server_cmd
        server_proc = monitor.ssh_spawn(server, server_cmd, bg=True)

        sleep(1)
        client = conf.address(conf.nginx.client)
        logging.info(f"Starting wrk on {client}")
        client_cmd = [
            "wrk",
            "-c", str(conf.nginx.connections),
            "-d", str(conf.nginx.duration),
            "-t", str(conf.nginx.client_threads),
            f"http://{server}:8123/",
        ]
        monitor.ssh_spawn(client, client_cmd)

        logging.info(f"Terminating server on {server}")
        monitor.ssh_spawn(server, ["killall", "nginx"])

# stub function for running bcpid
def bcpid_stub(ctx, func, server, exe, **kwargs):
    conf = ctx.obj.bcpid

    success = False
    enable = conf.enable
    proj_dir = conf.ghidra_proj_dir
    analyze = conf.analyze
    analyze_opts = conf.analyze_opts
    analyze_counter = conf.analyze_counter
    root_dir = conf.root_dir
    output_dir_prefix = conf.output_dir
    
    with Monitor(ctx.obj) as mon:
        while not success:
            randstr = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = str(os.path.join(output_dir_prefix, randstr))
            if enable:
                # start bcpid
                bcpid_start_cmd = ["sudo", "mkdir", "-p", output_dir, "&&",
                                    "cd", root_dir, "&&", 
                                    "sudo", "bcpid/bcpid", "-f", "-o", output_dir]
                
                logging.info("Starting bcpid...")
                proc_bcpid = mon.ssh_spawn(server, bcpid_start_cmd, bg=True)
                logging.info("Waiting for bcpid init...")
                sleep(10)

            success = func(ctx, mon, **kwargs)

            if enable:
                # stop bcpid
                bcpid_stop_cmd = mon.ssh_spawn(server, ["sudo", "killall", "bcpid"], bg=True, check=False)
                logging.info("Stopping bcpid...")
                mon.ssh_spawn(server, bcpid_stop_cmd, check=False)

                logging.info("Waiting for bcpid stop...")
                mon.wait(proc_bcpid)

                if not success:
                    # if our test failed, just restart the test
                    continue

                if (mon.get_return_code(proc_bcpid) != 0):
                    logging.warn(f"bcpid unexpected return code {mon.get_return_code(proc_bcpid)}...")
                    success = False
                else:
                    if analyze:
                        extract_cmd = ["cd", root_dir, "&&", "sudo", "bcpiquery/bcpiquery", "extract", 
                                        "-c", analyze_counter,
                                        "-p", output_dir]

                        logging.info("Extracting address info...")
                        mon.ssh_spawn(server, extract_cmd)

                        logging.info("Analyzing...")
                        analyze_cmd = [ "sudo", "mkdir", "-p", proj_dir, "&&", 
                                        "cd", root_dir, "&&", 
                                        "sudo", "scripts/analyze.sh", 
                                        proj_dir, str(os.path.join(root_dir, "address_info.csv")), exe]
                        if len(analyze_opts) > 0:
                            analyze_cmd.append(analyze_opts)
                        mon.ssh_spawn(server, analyze_cmd)
                        logging.info("Analysis done.")
                        




