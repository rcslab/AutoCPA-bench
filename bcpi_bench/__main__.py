#!/usr/bin/env python3

from .config import Config
from .spawn import spawn, ssh_spawn

import click
from contextlib import ExitStack
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

    for server in servers:
        address = ctx.obj.address(server)
        spawn(["ssh-copy-id", address])


@cli.command()
@click.argument('server', nargs=1)
@click.argument('command', nargs=-1)
@click.pass_context
def exec(ctx, server, command):
    """
    Execute a command on a server.
    """
    address = ctx.obj.address(server)
    ssh_spawn(address, command)


@cli.command()
@click.pass_context
def memcached(ctx):
    """
    Run the memcached benchmark.
    """

    conf = ctx.obj
    server = conf.address(conf.memcached.server)

    logging.info(f"Syncing code to server {server}")
    spawn(["rsync", "-aq", f"{ROOT_DIR}/.", f"{server}:bcpi-bench"])

    logging.info(f"Building code on {server}")
    ssh_spawn(server, ["make", "-C", "bcpi-bench", "-j12", "memcached", "mutilate"])

    with ExitStack() as stack:
        logging.info(f"Starting memcached on {server}")
        server_cmd = [
            "./bcpi-bench/memcached/memcached",
            "-m", "1024",
            "-c", "65536",
            "-b", "4096",
            "-t", str(conf.memcached.server_threads),
        ]
        server_proc = ssh_spawn(server, server_cmd, bg=True)
        stack.enter_context(server_proc)

        sleep(1)
        logging.info(f"Pre-loading data on {server}")
        ssh_spawn(server, ["./bcpi-bench/mutilate/mutilate", "--loadonly", "-s", "localhost"])

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
            clients.append(ssh_spawn(client_addr, client_cmd, bg=True))
            stack.enter_context(clients[-1])
            master_cmd += ["-a", client_addr]

        sleep(1)
        master = conf.address(conf.memcached.master)
        logging.info(f"Starting master on {master}")
        ssh_spawn(master, master_cmd)


@cli.command()
@click.pass_context
def nginx(ctx):
    """
    Run the nginx benchmark.
    """

    conf = ctx.obj
    server = conf.address(conf.nginx.server)

    logging.info(f"Syncing code to server {server}")
    #spawn(["rsync", "-aq", f"{ROOT_DIR}/.", f"{server}:bcpi-bench"])

    logging.info(f"Building code on {server}")
    #ssh_spawn(server, ["make", "-C", "bcpi-bench", "-j12", "nginx"])

    with ExitStack() as stack:
        # Set up the nginx working directory
        logging.info(f"Starting nginx on {server}")
        ssh_spawn(server, ["rm", "-rf", conf.nginx.prefix])
        ssh_spawn(server, ["mkdir", "-p", conf.nginx.prefix + "/conf", conf.nginx.prefix + "/logs"])
        ssh_spawn(server, ["cp", "./bcpi-bench/" + conf.nginx.config, conf.nginx.prefix + "/conf"])
        ssh_spawn(server, ["cp", "./bcpi-bench/nginx/docs/html/index.html", conf.nginx.prefix])

        server_cmd = [
            "./bcpi-bench/nginx/objs/nginx",
            "-e", "stderr",
            "-p", conf.nginx.prefix,
        ]
        server_proc = ssh_spawn(server, server_cmd, bg=True)
        stack.enter_context(server_proc)

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
        ssh_spawn(client, client_cmd)

        server_proc.terminate()
