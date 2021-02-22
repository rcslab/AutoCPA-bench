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
class Config:
    """
    bcpi_bench configuration (see cluster.conf).
    """

    servers: Dict[str, Server]
    memcached: MemcachedConfig
    nginx: NginxConfig

    @classmethod
    def load(cls, file):
        return cls(toml.load(file))

    def __init__(self, data):
        self.servers = {}
        for key, server in data["servers"].items():
            self.servers[key] = Server(**server)

        self.memcached = MemcachedConfig(**data["memcached"])
        self.nginx = NginxConfig(**data["nginx"])

    def address(self, server):
        """
        Get the address of a named server.
        """
        return self.servers[server].address
