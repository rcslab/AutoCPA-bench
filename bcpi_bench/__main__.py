#!/usr/bin/env python3

from .config import Config
from .monitor import Monitor

import click
import logging
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

    logging.basicConfig(level=getattr(logging, log.upper()))

    ctx.obj = Config.load(conf)


@cli.command()
@click.argument('servers', nargs=-1)
@click.pass_context
def ssh_copy_id(ctx, servers):
    """
    Install your public key on the given servers (default: all).
    """

    if not servers:
        servers = list(ctx.obj.servers.keys())

    with Monitor() as monitor:
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

    with Monitor() as monitor:
        address = ctx.obj.address(server)
        monitor.ssh_spawn(address, command)


def _sync_build(monitor, server, targets, sync=True, build=True):
    """
    Sync and build the code on a server.
    """

    if sync:
        logging.info(f"Syncing code to server {server}")
        monitor.spawn(["rsync", "-aq", f"{ROOT_DIR}/.", f"{server}:bcpi-bench"])

    if build:
        logging.info(f"Building code on {server}")
        monitor.ssh_spawn(server, ["make", "-C", "bcpi-bench", "-j12"] + list(targets))


@cli.command()
@click.option("--sync/--no-sync", default=True, help="Sync the code to the server")
@click.argument('server', nargs=1)
@click.argument('targets', nargs=-1)
@click.pass_context
def build(ctx, sync, server, targets):
    """
    Build the code on a server.
    """

    conf = ctx.obj

    with Monitor() as monitor:
        _sync_build(monitor, conf.address(server), targets, sync=sync)


@cli.command()
@click.option("--sync/--no-sync", default=True, help="Sync the code to the servers")
@click.option("--build/--no-build", default=True, help="Build the code on the servers")
@click.option("--pmc-stat/--no-pmc-stat", default=False, help="Run the benchmark under pmc stat")
@click.pass_context
def memcached(ctx, sync, build, pmc_stat):
    """
    Run the memcached benchmark.
    """

    conf = ctx.obj
    server = conf.address(conf.memcached.server)

    with Monitor() as monitor:
        _sync_build(monitor, server, ["memcached", "mutilate"], sync=sync, build=build)

        logging.info(f"Starting memcached on {server}")
        server_cmd = [
            "./bcpi-bench/memcached/memcached",
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
        monitor.ssh_spawn(server, ["./bcpi-bench/mutilate/mutilate", "--loadonly", "-s", "localhost"])

        master_cmd = [
            "./bcpi-bench/mutilate/mutilate",
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
            "./bcpi-bench/mutilate/mutilate",
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

    with Monitor() as monitor:
        _sync_build(monitor, server, ["nginx"], sync=sync, build=build)

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


@cli.command()
@click.option("--sync/--no-sync", default=True, help="Sync the code to the servers")
@click.option("--build/--no-build", default=True, help="Build the code on the servers")
@click.option("--pmc-stat/--no-pmc-stat", default=False, help="Run the benchmark under pmc stat")
@click.pass_context
def lighttpd(ctx, sync, build, pmc_stat):
    """
    Run the lighttpd benchmark.
    """

    conf = ctx.obj
    server = conf.address(conf.lighttpd.server)

    with Monitor() as monitor:
        _sync_build(monitor, server, ["lighttpd"], sync=sync, build=build)

        # Set up the lighttpd working directory
        logging.info(f"Starting lighttpd on {server}")
        monitor.ssh_spawn(server, ["rm", "-rf", conf.lighttpd.webroot])
        monitor.ssh_spawn(server, ["mkdir", "-p", conf.lighttpd.webroot])
        monitor.ssh_spawn(server, ["cp", "./bcpi-bench/lighttpd/tests/docroot/www/index.html", conf.lighttpd.webroot])

        server_cmd = [
            "./bcpi-bench/lighttpd/sconsbuild/static/build/lighttpd",
            "-f", "./bcpi-bench/" + conf.lighttpd.config,
            "-D",
        ]
        if pmc_stat:
            server_cmd = ["pmc", "stat", "--"] + server_cmd
        server_proc = monitor.ssh_spawn(server, server_cmd, bg=True)

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
        monitor.ssh_spawn(server, ["killall", "lighttpd"])
