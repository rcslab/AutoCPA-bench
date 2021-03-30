#!/usr/bin/env python3

"""
Cluster configuration.
"""

from dataclasses import dataclass
import toml
from typing import Dict, List


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
class CommonConfig:
    """
    common config
    """

    remote_dir: str
    local_dir: str
    monitor_verbose: int

@dataclass
class BcpidConfig:
    """
    bcpid config
    """
    enable: int
    root_dir: str
    ghidra_proj_dir: str
    analyze: int
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
    client: str
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
    client: str
    client_threads: int
    connections: int
    duration: float


@dataclass
class Config:
    """
    bcpi_bench configuration (see cluster.conf).
    """

    servers: Dict[str, Server]
    memcached: MemcachedConfig
    nginx: NginxConfig
    rocksdb: RocksdbConfig
    bcpid: BcpidConfig
    common: CommonConfig
    pkg: PkgConfig
    lighttpd: LighttpdConfig

    @classmethod
    def load(cls, file):
        return cls(**toml.load(file))

    def __init__(self, servers, common, pkg, bcpid, memcached, nginx, rocksdb, lighttpd):
        self.servers = {}
        for key, server in servers.items():
            self.servers[key] = Server(**server)

        self.memcached = MemcachedConfig(**memcached)
        self.nginx = NginxConfig(**nginx)
        self.rocksdb = RocksdbConfig(**rocksdb)
        self.common = CommonConfig(**common)
        self.bcpid = BcpidConfig(**bcpid)
        self.pkg = PkgConfig(**pkg)
        self.lighttpd = LighttpdConfig(**lighttpd)

    def address(self, server):
        """
        Get the address of a named server.
        """
        return self.servers[server].address
