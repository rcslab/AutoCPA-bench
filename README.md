BCPI Benchmarks
===============

This repository contains the benchmarks and expirements for BCPI.


Getting started
---------------

Everything is controlled by the `cluster.py` script.
The first time you run `./cluster.py`, it will even create a Python virtual environment for itself and install its own dependencies.
Once that finishes, you'll see usage information:

    Usage: cluster.py [OPTIONS] COMMAND [ARGS]...

      Control the BCPI benchmarking cluster.

    Options:
      -c, --conf FILENAME  configuration file
      -l, --log TEXT       log level
      --help               Show this message and exit.

    Commands:
      build        Build the code on a server.
      exec         Execute a command on a server.
      memcached    Run the memcached benchmark.
      nginx        Run the nginx benchmark.
      ssh-copy-id  Install your public key on the given servers (default: all).

`cluster.py` uses `ssh` to run things on the servers in the cluster.
This works best if your public key is authorized on the servers.
You can run

    $ ./cluster.py ssh-copy-id

to authorize yourself on all the servers if necessary.
Run

    $ ./cluster.py exec skylake2 -- echo Hello world

to make sure it's working.


Running benchmarks
------------------

If everything's working properly, you should be able to run a benchmark with a single command, e.g.

    $ ./cluster.py memcached

This will automatically sync the code to the server(s), build it, run it, and spin up clients to benchmark it.
The standard output/error streams of every process it spawns will be saved under `./logs/<DATE>/<TIME>/*.std{out,err}`.

The benchmarks are configured by the `cluster.conf` file (see below).
They may also support command-line flags to control their behaviour.
See the `--help` output for details:

    $ ./cluster.py memcached --help
    Usage: cluster.py memcached [OPTIONS]

      Run the memcached benchmark.

    Options:
      --sync / --no-sync          Sync the code to the servers
      --build / --no-build        Build the code on the servers
      --pmc-stat / --no-pmc-stat  Run the benchmark under pmc stat
      --help                      Show this message and exit.


Configuration
-------------

`cluster.conf` is a [TOML](https://toml.io/) file that configures the cluster and the individual benchmarks.
To add a new server, add a block like this:

    [servers.alderlake1]
    address = "alderlake1.rcs.uwaterloo.ca"

Benchmark-specific details are configured under the appropriate heading, e.g. `[memcached]` or `[nginx]`.
See `cluster.conf` for details.


Adding benchmarks
-----------------

New benchmarks must be set up in a few places:

- The various programs we benchmark are added as git subtrees.
  To add the code for a new benchmark, first add its git repo as a remote:

      $ git remote add nginx "https://github.com/nginx/nginx.git"
      $ git fetch nginx
      remote: Enumerating objects: 92, done.
      remote: Counting objects: 100% (92/92), done.
      remote: Total 139 (delta 92), reused 92 (delta 92), pack-reused 47
      Receiving objects: 100% (139/139), 182.02 KiB | 3.64 MiB/s, done.
      Resolving deltas: 100% (108/108), completed with 26 local objects.
      From https://github.com/nginx/nginx
         ef4462785..02cca5477  branches/default -> nginx/branches/default
         ef4462785..02cca5477  master           -> nginx/master
       * [new tag]             release-1.19.8   -> release-1.19.8

  Then add the subtree:

      $ git subtree add -P nginx nginx release-1.19.8 --squash
      git fetch nginx release-1.19.8
      From https://github.com/nginx/nginx
       * tag                   release-1.19.8 -> FETCH_HEAD
      Added dir 'nginx'

  This will create a commit that adds the code as a subtree.
  It's important to avoid squashing that commit, since it has metadata that `git subtree` will need for future operations, like updating the subtree:

      $ git subtree pull -P nginx nginx release-1.19.8 --squash
      From https://github.com/nginx/nginx
       * tag                   release-1.19.8 -> FETCH_HEAD
      Merge made by the 'recursive' strategy.

- Configuration is stored in `cluster.conf`.
  The Python representation is found in `bcpi_bench/config.py`.
  Add the appropriate class, e.g. `NginxConfig`, and wire it up to the root `Config` object in `Config.__init__()`.

- The benchmark drivers are implemented in `bcpi_bench/__main__.py`.
  Add a new function for your benchmark, and wire it up as a subcommand with [Click](https://click.palletsprojects.com/).
  See the existing benchmarks for details.
