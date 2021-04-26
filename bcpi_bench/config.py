#!/usr/bin/env python3

"""
Cluster configuration.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import jinja2
import os
import toml


@dataclass
class Server:
    """
    A server in the cluster.
    """

    address: str


@dataclass
class PkgConfig:
    """
    pkg config
    """
    servers: List[str]
    pkg: List[str]
    pkg_rm: List[str]


@dataclass
class PmcConfig:
    """
    pmc config
    """
    counters: List[str]
    counters_per_batch: int


@dataclass
class BcpidConfig:
    """
    bcpid config
    """
    root_dir: str
    ghidra_proj_dir: str
    analyze_opts: str
    analyze_counter: str
    output_dir: str


@dataclass
class MemcachedConfig:
    """
    memcached benchmark configuration.
    """

    server: str
    master: str
    clients: List[str]
    server_threads: int
    client_threads: int
    warmup: float
    duration: float
    connections_per_thread: int


@dataclass
class NginxConfig:
    """
    nginx benchmark configuration.
    """

    config: str
    prefix: str
    server: str
    clients: List[str]
    client_threads: int
    connections: int
    duration: float


@dataclass
class RocksdbConfig:
    """
    rocksdb benchmark configuration.
    """

    server: str
    db_directory: str
    master: str
    clients: List[str]
    server_threads: int
    client_threads: int
    warmup: int
    duration: int
    connections_per_thread: int
    affinity: int
    qps: int
    master_qps: int
    master_connections: int
    master_threads: int


@dataclass
class LighttpdConfig:
    """
    lighttpd benchmark configuration.
    """

    config: str
    webroot: str
    server: str
    clients: List[str]
    client_threads: int
    connections: int
    duration: float


@dataclass
class MysqlConfig:
    """
    MySQL benchmark configuration.
    """

    datadir: str
    plugin_dir: str
    server: str
    clients: List[str]
    client_threads: int


@dataclass
class RedisConfig:
    """
    Redis configuration.
    """
    prefix: str
    clients: List[str]
    server: str
    duration: int
    depth: int
    client_threads: int
    client_connections: int


@dataclass
class Config:
    """
    bcpi_bench configuration (see cluster.conf).
    """

    local_dir: str
    output_dir: str
    remote_dir: str
    verbose: bool

    servers: Dict[str, Server]

    memcached: MemcachedConfig
    nginx: NginxConfig
    rocksdb: RocksdbConfig
    bcpid: BcpidConfig
    pkg: PkgConfig
    lighttpd: LighttpdConfig
    mysql: MysqlConfig

    def render(self, doc):
        return jinja2.Template(doc).render(conf=self._conf_obj)

    @classmethod
    def load(cls, file):
        buf = file.read()
        obj = toml.loads(buf)

        while True:
            new_buf = jinja2.Template(buf).render(conf=obj)
            if new_buf == buf:
                break
            buf = new_buf

        return cls(toml.loads(buf))

    def __init__(self, toml_obj):
        self._conf_obj = toml_obj

        self.local_dir = toml_obj["local_dir"]
        self.remote_dir = toml_obj["remote_dir"]
        self.verbose = toml_obj.get("verbose", False)

        now = datetime.utcnow().isoformat(sep="/")
        self.output_dir = str(Path(f"{self.local_dir}/{now}").expanduser().resolve())

        self.servers = {}
        for key, server in toml_obj["servers"].items():
            self.servers[key] = Server(**server)

        self.memcached = MemcachedConfig(**toml_obj["memcached"])
        self.nginx = NginxConfig(**toml_obj["nginx"])
        self.rocksdb = RocksdbConfig(**toml_obj["rocksdb"])

        self.bcpid = BcpidConfig(**toml_obj["bcpid"])
        self.pkg = PkgConfig(**toml_obj["pkg"])
        self.lighttpd = LighttpdConfig(**toml_obj["lighttpd"])
        self.mysql = MysqlConfig(**toml_obj["mysql"])
        self.redis = RedisConfig(**toml_obj["redis"])
        self.pmc = PmcConfig(**toml_obj["pmc"])
        self.pmc.prefix = []

    def address(self, server):
        """
        Get the address of a named server.
        """
        return self.servers[server].address
