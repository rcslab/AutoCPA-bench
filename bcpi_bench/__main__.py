#!/usr/bin/env python3

from .config import Config
from .monitor import Monitor
from .parser import *

from pathlib import Path
from tempfile import NamedTemporaryFile
from time import sleep

import click
import datetime
import logging
import os
import subprocess
import sys


ROOT_DIR = Path(__file__).resolve().parent.parent


def remote_render(ctx, mon, input, server, output):
    """
    Render {input} using Config and scp it to remote {server}:{output}
    """

    conf = ctx.obj

    with open(input, "r") as f:
        buf = f.read()

    buf = conf.render(buf)

    with NamedTemporaryFile(mode="w+") as f:
        f.write(buf)
        f.flush()

        mon.spawn(["scp", f.name, f"{server}:{output}"])


def pmc_loop(ctx, mon, server, func, **kwargs):
    conf = ctx.obj
    pmc_idx = 0

    if (len(conf.pmc.counters) == 0 or conf.pmc.counters_per_batch <= 0):
        raise Exception("No pmc counters defined or invalid counters per batch #.")

    mon.ssh_spawn(server, ["sudo", "sysctl", "security.bsd.unprivileged_proc_debug=1"])
    mon.ssh_spawn(server, ["sudo", "sysctl", "security.bsd.unprivileged_syspmcs=1"])

    while pmc_idx < len(conf.pmc.counters):
        # passing pmc prefix like this is pretty hacky
        # another way is to let Monitor handle prefixes/suffixes
        # i.e. for pmc runs we pass a Monitor with prefix "pmc stat ..."
        #      and for normal runs we pass a Monitor with empty prefix
        # but this breaks Monitor's modularity a bit
        conf.pmc.prefix.clear()
        conf.pmc.prefix.extend(["pmc", "stat", "-j"])
        pmc_batch_items = min(len(conf.pmc.counters) - pmc_idx, conf.pmc.counters_per_batch)

        pmc_batch_str = ""
        for i in range(0, pmc_batch_items):
            pmc_batch_str += conf.pmc.counters[pmc_idx + i]
            pmc_batch_str += ','
        pmc_batch_str = pmc_batch_str[:-1]
        pmc_idx = pmc_idx + pmc_batch_items
        conf.pmc.prefix.extend([pmc_batch_str, "--"])

        logging.info("Running with pmc prefix " + str(conf.pmc.prefix))

        success = False
        while not success:
            success = func(ctx, mon, **kwargs)

    # clear pmc settings for runs without pmc
    conf.pmc.prefix.clear()

def bcpid_loop(ctx, mon, func, server, exe, **kwargs):
    conf = ctx.obj

    success = False
    proj_dir = conf.bcpid.ghidra_proj_dir
    analyze = conf.bcpid.analyze
    analyze_opts = conf.bcpid.analyze_opts
    analyze_counter = conf.bcpid.analyze_counter
    root_dir = conf.bcpid.root_dir
    bcpid_output_dir_prefix = conf.bcpid.output_dir
    output_dir = conf.output_dir
    bcpid_stop_cmd = ["sudo", "killall", "bcpid"]
    proj_name = Path(exe).name

    while not success:
        # new folder for each run
        randstr = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        bcpid_output_dir = f"{bcpid_output_dir_prefix}/{randstr}"

        # stop bcpid
        logging.info("Stopping bcpid...")
        stop_proc = mon.ssh_spawn(server, bcpid_stop_cmd, check=False)
        logging.info("Waiting for bcpid stop...")
        sleep(10)
        mon.wait(stop_proc)

        # start bcpid
        bcpid_start_cmd  = ["sh", "-c", f"mkdir -p {bcpid_output_dir} && cd {root_dir} && " +
                            f"bcpid/bcpid -f -o {bcpid_output_dir}"]

        logging.info("Starting bcpid...")
        proc_bcpid = mon.ssh_spawn(server, bcpid_start_cmd, bg=True)
        logging.info("Waiting for bcpid init...")
        sleep(10)

        success = func(ctx, mon, **kwargs)

        # stop bcpid
        logging.info("Stopping bcpid...")
        mon.ssh_spawn(server, bcpid_stop_cmd, check=False)

        logging.info("Waiting for bcpid stop...")
        mon.check_success(proc_bcpid)

        if not success:
            # if our test failed, just restart the test
            # this could happen when running multiple clients against the server
            # sometimes some connections will be dropped on handshake (see the logic in _rocksdb())
            # if so, restart bcpid too for accuracy
            logging.info("Test function returned failure. Re-running...")
            continue

        logging.info("Copying bcpid records...")
        mon.spawn(["mkdir", "-p", f"{output_dir}/bcpid/"])
        mon.spawn(["scp", f"{server}:{bcpid_output_dir}/*", f"{output_dir}/bcpid/"])

        if (mon.get_return_code(proc_bcpid) != 0):
            logging.warn(f"bcpid unexpected return code {mon.get_return_code(proc_bcpid)}...")
            success = False
        else:
            if analyze:
                extract_cmd = [ "sh", "-c", f"cd {root_dir} && bcpiquery/bcpiquery extract -c {analyze_counter}" +
                    f"-p {bcpid_output_dir} -o {exe}"]

                logging.info("Extracting address info...")
                mon.ssh_spawn(server, extract_cmd)

                addr_info_scp_cmd = ["scp", f"{server}:{root_dir}/address_info.csv", f"{output_dir}/"]
                logging.info("Copying address info...")
                mon.spawn(addr_info_scp_cmd)

                logging.info("Analyzing...")
                analyze_cmd = [ "sh", "-c", f"mkdir -p {proj_dir} && " +
                                f"cd {root_dir} && " +
                                f"scripts/analyze.sh {proj_dir} {root_dir}/address_info.csv {exe}"]
                if len(analyze_opts) > 0:
                    analyze_cmd.append(analyze_opts)
                mon.ssh_spawn(server, analyze_cmd)

                logging.info("Analysis done, copying projects...")
                analysis_scp_cmd = ["scp", "-r", f"{server}:{proj_dir}/{proj_name}.rep", f"{output_dir}/"]
                mon.spawn(analysis_scp_cmd)

# stub function for handling bcpid and pmc
def bcpid_stub(ctx, func, server, exe, **kwargs):
    conf = ctx.obj

    with Monitor(ctx.obj) as mon:
        if conf.pmc.enable:
            logging.info("Running pmc loop...")
            pmc_loop(ctx, mon, server, func, **kwargs)
        if conf.bcpid.enable:
            logging.info("Running bcpid loop...")
            bcpid_loop(ctx, mon, func, server, exe, **kwargs)
        if (not conf.pmc.enable) and (not conf.bcpid.enable):
            logging.info("Running regular loop...")
            # only run regular test when pmc and bcpid are both disabled
            while True:
                if func(ctx, mon, **kwargs):
                    break

@click.group()
@click.option(
    "-c", "--conf",
    default=ROOT_DIR/"cluster.conf",
    type=click.File("r"),
    help="Configuration file"
)
@click.option("-l", "--log", default="INFO", type=str, help="Log level")
@click.option("-v", "--verbose", is_flag=True, help="Show foreground process output (default: false)")
@click.option("--pmc/--no-pmc", default=False, type=bool, help="Collect pmc stat output (default: false)")
@click.option("--bcpid/--no-bcpid", default=False, type=bool, help="Enable bcpid (default: false)")
@click.option("--analyze/--no-analyze", default=False, type=bool, help="Enable analysis (default: false, requires --bcpid)")
@click.pass_context
def cli(ctx, conf, log, verbose, pmc, bcpid, analyze):
    """
    Control the BCPI benchmarking cluster.
    """

    config = Config.load(conf)
    config.pmc.enable = pmc
    config.bcpid.enable = bcpid
    config.bcpid.analyze = analyze
    config.verbose = verbose
    ctx.obj = config

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, log.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(output_dir/"log.txt"),
        ]
    )


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

    remote_dir = f"{conf.remote_dir}/bcpi-bench"

    if len(targets) == 0:
        targets = []
        targets.append("all")

    full_addresses = []
    if server != None:
        full_addresses.append(conf.address(server))
    else:
        for each in conf.pkg.servers:
            full_addresses.append(conf.address(each))

    with Monitor(conf) as monitor:
        if sync:
            logging.info(f"Syncing code...")
            monitor.ssh_spawn_all(full_addresses, ["mkdir", "-p", remote_dir])

            rsync_bg = len(full_addresses) > 1
            procs = []
            for addr in full_addresses:
                procs.append(monitor.spawn(["rsync", "-az", "--info=progress2", "--exclude=.git", f"{ROOT_DIR}/.", f"{addr}:{remote_dir}"], bg=rsync_bg, check=False))
            monitor.check_success_all(procs)

        if clean:
            logging.info(f"Cleaning...")
            monitor.ssh_spawn_all(full_addresses, ["make", "-C", f"{remote_dir}"] + list("clean-" + t for t in targets))

        if build:
            logging.info(f"Building...")
            monitor.ssh_spawn_all(full_addresses, ["make", "-C", f"{remote_dir}", "-j48"] + list(targets))


@cli.command()
@click.pass_context
def rocksdb(ctx, **kwargs):
    """
    Run the rocksdb benchmark.
    """

    conf = ctx.obj
    bcpid_stub(ctx, _rocksdb, conf.address(conf.rocksdb.server),
                f"{conf.remote_dir}/bcpi-bench/kqsched/pingpong/build/ppd", **kwargs)

def _rocksdb(ctx, monitor):
    success = False
    conf = ctx.obj
    rdb_conf = conf.rocksdb
    sample_output = f"{conf.remote_dir}/bcpi-bench/kqsched/pingpong/build/sample.txt"
    local_sample = f"{conf.output_dir}/rocksdb_sample.txt"

    server = conf.address(rdb_conf.server)
    master = conf.address(rdb_conf.master)
    ppd_exe = f"{conf.remote_dir}/bcpi-bench/kqsched/pingpong/build/ppd"
    dismember_exe = f"{conf.remote_dir}/bcpi-bench/kqsched/pingpong/build/dismember"
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
    proc_ppd = monitor.ssh_spawn(server, conf.pmc.prefix + ppd_cmd, bg=True)

    # start clients
    procs_client = []
    client_cmd = [dismember_exe, "-A"]
    logging.info(f"Starting clients...")
    for client in rdb_conf.clients:
        procs_client.append(monitor.ssh_spawn(conf.address(client), client_cmd, bg=True))

    sleep(3)
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

        sleep(1)
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
    procs = mon.ssh_spawn_all(targets, ["sudo", "killall", "ppd"], bg=True)
    procs.extend(mon.ssh_spawn_all(targets, ["sudo", "killall", "dismember"], bg=True))
    mon.wait_all(procs)

def _rocksdb_checkerr(mon : Monitor, targets):
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
    Install required pkgs on servers.
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

    with Monitor(conf) as mon:
        cmd = ["sudo", "pkg", "update"]
        mon.ssh_spawn_all(full_addresses, cmd)

        if upgrade:
            cmd = ["sudo", "pkg", "upgrade", "-y"]
            mon.ssh_spawn_all(full_addresses, cmd)

        cmd = ["sudo", "pkg", "remove", "-y"] + list(pkg_conf.pkg_rm)
        mon.ssh_spawn_all(full_addresses, cmd)

        cmd = ["sudo", "pkg", "install", "-y"] + list(pkg_conf.pkg)
        mon.ssh_spawn_all(full_addresses, cmd)


@cli.command()
@click.pass_context
def memcached(ctx, **kwargs):
    """
    Run the memcached benchmark.
    """

    conf = ctx.obj
    bcpid_stub(ctx, _memcached, conf.address(conf.memcached.server),
                f"{conf.remote_dir}/bcpi-bench/memcached/memcached", **kwargs)

def _memcached(ctx, monitor):
    conf = ctx.obj
    server = conf.address(conf.memcached.server)
    memcached_exe = f"{conf.remote_dir}/bcpi-bench/memcached/memcached"
    mutilate_exe = f"{conf.remote_dir}/bcpi-bench/mutilate/mutilate"

    monitor.ssh_spawn(server, ["killall", "memcached"], check=False)
    sleep(1)

    logging.info(f"Starting memcached on {server}")
    server_cmd = [
        memcached_exe,
        "-m", "1024",
        "-c", "65536",
        "-b", "4096",
        "-t", str(conf.memcached.server_threads),
    ]
    server_proc = monitor.ssh_spawn(server, conf.pmc.prefix + server_cmd, bg=True)

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

    return True


@cli.command()
@click.pass_context
def nginx(ctx, **kwargs):
    """
    Run the nginx benchmark.
    """

    conf = ctx.obj
    bcpid_stub(ctx, _nginx, conf.address(conf.nginx.server),
                f"{conf.remote_dir}/bcpi-bench/nginx/objs/nginx", **kwargs)

def _nginx(ctx, monitor):
    conf = ctx.obj
    server = conf.address(conf.nginx.server)

    # Set up the nginx working directory
    logging.info(f"Starting nginx on {server}")
    monitor.ssh_spawn(server, ["rm", "-rf", conf.nginx.prefix])
    monitor.ssh_spawn(server, ["mkdir", "-p", conf.nginx.prefix + "/conf", conf.nginx.prefix + "/logs"])
    remote_render(ctx, monitor, f"{ROOT_DIR}/nginx.conf", server, conf.nginx.prefix + "/conf/nginx.conf")
    monitor.ssh_spawn(server, ["cp", f"{conf.remote_dir}/bcpi-bench/nginx/docs/html/index.html", conf.nginx.prefix])

    server_cmd = [
        f"{conf.remote_dir}/bcpi-bench/nginx/objs/nginx",
        "-e", "stderr",
        "-p", conf.nginx.prefix,
    ]
    server_proc = monitor.ssh_spawn(server, conf.pmc.prefix + server_cmd, bg=True)

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

    return True

@cli.command()
@click.pass_context
def lighttpd(ctx, **kwargs):
    """
    Run the lighttpd benchmark.
    """

    conf = ctx.obj
    bcpid_stub(ctx, _lighttpd, conf.address(conf.lighttpd.server),
                f"{conf.remote_dir}/bcpi-bench/lighttpd/sconsbuild/static/build/lighttpd", **kwargs)

def _lighttpd(ctx, monitor):
    conf = ctx.obj
    server = conf.address(conf.lighttpd.server)

    # Set up the lighttpd working directory
    logging.info(f"Starting lighttpd on {server}")
    monitor.ssh_spawn(server, ["rm", "-rf", conf.lighttpd.webroot])
    monitor.ssh_spawn(server, ["mkdir", "-p", conf.lighttpd.webroot])
    monitor.ssh_spawn(server, ["cp", f"{conf.remote_dir}/bcpi-bench/lighttpd/tests/docroot/www/index.html", conf.lighttpd.webroot])
    remote_render(ctx, monitor, f"{ROOT_DIR}/lighttpd.conf", server, conf.lighttpd.webroot + "/lighttpd.conf")

    server_cmd = [
        f"{conf.remote_dir}/bcpi-bench/lighttpd/sconsbuild/static/build/lighttpd",
        "-f", f"{conf.lighttpd.webroot}/lighttpd.conf",
        "-D",
    ]
    server_proc = monitor.ssh_spawn(server, conf.pmc.prefix + server_cmd, bg=True)

    sleep(1)
    client = conf.address(conf.lighttpd.client)
    logging.info(f"Starting wrk on {client}")
    client_cmd = [
        "wrk",
        "-c", str(conf.lighttpd.connections),
        "-d", str(conf.lighttpd.duration),
        "-t", str(conf.lighttpd.client_threads),
        f"http://{server}:8123/",
    ]
    monitor.ssh_spawn(client, client_cmd)

    logging.info(f"Terminating server on {server}")
    monitor.ssh_spawn(server, ["sudo", "killall", "lighttpd"])

    return True

@cli.command()
@click.pass_context
def mysql(ctx, **kwargs):
    """
    Run the MySQL benchmark.
    """

    conf = ctx.obj
    bcpid_stub(ctx, _mysql, conf.address(conf.mysql.server),
                f"{conf.remote_dir}/bcpi-bench/mysql-server/build/bin/mysqld", **kwargs)

def _mysql(ctx, monitor):
    conf = ctx.obj
    server = conf.address(conf.lighttpd.server)

    logging.info(f"Starting mysql on {server}")
    monitor.ssh_spawn(server, ["rm", "-rf", conf.mysql.datadir])
    monitor.ssh_spawn(server, ["mkdir", "-p", conf.mysql.datadir])

    server_cmd = [
        f"{conf.remote_dir}/bcpi-bench/mysql-server/build/bin/mysqld",
        "--no-defaults",
        f"--datadir={conf.mysql.datadir}",
        f"--plugin-dir={conf.mysql.plugin_dir}",
    ]

    monitor.ssh_spawn(server, server_cmd + ["--initialize-insecure"])

    server_proc = monitor.ssh_spawn(server, conf.pmc.prefix + server_cmd, bg=True)

    sleep(5)
    logging.info(f"Creating test database")
    monitor.ssh_spawn(server, ["mysql", "-u", "root", "-e",
        "CREATE DATABASE sbtest; CREATE USER sbtest@'%'; GRANT ALL PRIVILEGES ON sbtest.* TO sbtest@'%';"])

    sleep(1)
    client = conf.address(conf.lighttpd.client)
    logging.info(f"Starting sysbench on {client}")
    client_cmd = [
        "sysbench",
        "/usr/local/share/sysbench/oltp_read_write.lua",
        "--db-driver=mysql",
        f"--mysql-host={server}",
        f"--mysql-user=sbtest",
        f"--threads={conf.mysql.client_threads}",
    ]

    monitor.ssh_spawn(client, client_cmd + ["prepare"])
    monitor.ssh_spawn(client, client_cmd + ["run"])

    logging.info(f"Terminating server on {server}")
    monitor.ssh_spawn(server, ["sudo", "killall", "mysqld"])

    return True


@cli.command()
@click.pass_context
def redis(ctx, **kwargs):
    """
    Run the redis benchmark.
    """

    conf = ctx.obj
    bcpid_stub(ctx, _redis, conf.address(conf.redis.server),
                f"{conf.remote_dir}/bcpi-bench/redis/src/redis-server",**kwargs)

def _redis(ctx, monitor):
    conf = ctx.obj
    server = conf.address(conf.redis.server)
    redis_exe = f"{conf.remote_dir}/bcpi-bench/redis/src/redis-server"
    memtier = f"{conf.remote_dir}/bcpi-bench/memtier/memtier_benchmark"
    client = conf.address(conf.redis.client)

    logging.info(f"Terminating redis on {server}")
    monitor.ssh_spawn(server, ["sudo", "killall", "-9","redis-server"], check=False)
    logging.info(f"Terminating memtier on {client}")
    monitor.ssh_spawn(client, ["sudo", "killall", "-9","memtier_benchmark"], check=False)

    sleep(1)
    logging.info(f"Starting redis on {server}")
    server_cmd = [
        redis_exe,
        f"{conf.remote_dir}/bcpi-bench/redis.conf"
    ]
    server_proc = monitor.ssh_spawn(server, conf.pmc.prefix + server_cmd, bg=True)

    sleep(1)
    logging.info(f"Pre-loading data on {server}")
    monitor.ssh_spawn(server, [memtier, "-n", "allkeys", "-s", "localhost", "-R", "--key-pattern=P:P", "--ratio=1:0"])

    logging.info(f"Starting client on {client}")
    monitor.ssh_spawn(client, ["sudo", "rm", "-rf", conf.redis.prefix])
    monitor.ssh_spawn(client, ["mkdir", "-p", conf.redis.prefix])
    client_cmd = [
        memtier,
        "-s", server,
        "-t", str(conf.redis.client_threads),
        "-R",
        "-c", str(conf.redis.client_connections),
        f"--pipeline={conf.redis.depth}",
        f"--test-time={conf.redis.duration}",
        "-o", f"{conf.redis.prefix}/memtier.txt"
    ]
    monitor.ssh_spawn(client, client_cmd)

    logging.info(f"Terminating memtier on {client}")
    monitor.ssh_spawn(client, ["sudo", "killall", "-9", "memtier_benchmark"], check=False)
    logging.info(f"Terminating redis on {server}")
    monitor.ssh_spawn(server, ["sudo", "killall", "-9", "redis-server"], check=False)

    return True
