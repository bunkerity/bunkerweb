#!/usr/bin/env python3

from pathlib import Path
from sys import path, argv, exit
from glob import glob
from os import _exit, getenv
from os.path import isfile
from traceback import format_exc
from json import loads, dumps
from subprocess import run

path.extend((f"{Path.cwd()}/utils", f"{Path.cwd()}/tests"))

from DockerTest import DockerTest
from AutoconfTest import AutoconfTest
from SwarmTest import SwarmTest
from KubernetesTest import KubernetesTest
from LinuxTest import LinuxTest
from Test import Test
from logger import log

if len(argv) <= 1:
    log("TESTS", "❌", "Missing type argument")
    exit(1)

test_type = argv[1]
if test_type not in ("linux", "docker", "autoconf", "swarm", "kubernetes", "ansible"):
    log("TESTS", "❌", "Wrong type argument " + test_type)
    exit(1)

run("docker system prune", shell=True)

log("TESTS", "ℹ️", "Starting tests for " + test_type + " ...")
ret = False
end_fun = None
if test_type == "docker":
    ret = DockerTest.init()
    end_fun = DockerTest.end
elif test_type == "autoconf":
    ret = AutoconfTest.init()
    end_fun = AutoconfTest.end
elif test_type == "swarm":
    ret = SwarmTest.init()
    end_fun = SwarmTest.end
elif test_type == "kubernetes":
    ret = KubernetesTest.init()
    end_fun = KubernetesTest.end
elif test_type == "linux":
    distro = argv[2]
    ret = LinuxTest.init(distro)
    end_fun = LinuxTest.end
if not ret:
    log("TESTS", "❌", "Test.init() failed")
    exit(1)

domains = {}
if test_type in ["docker", "autoconf", "linux"]:
    domains = {
        "www.example.com": Test.random_string(6) + "." + getenv("TEST_DOMAIN1"),
        "auth.example.com": Test.random_string(6) + "." + getenv("TEST_DOMAIN1"),
        "app1.example.com": Test.random_string(6) + "." + getenv("TEST_DOMAIN1_1"),
        "app2.example.com": Test.random_string(6) + "." + getenv("TEST_DOMAIN1_2"),
        "app3.example.com": Test.random_string(6) + "." + getenv("TEST_DOMAIN1_3"),
    }
elif test_type == "kubernetes":
    domains = {
        "www.example.com": Test.random_string(6) + "." + getenv("TEST_DOMAIN1_2"),
        "auth.example.com": Test.random_string(1) + "." + getenv("TEST_DOMAIN1_2"),
        "app1.example.com": Test.random_string(6) + "." + getenv("TEST_DOMAIN1"),
        "app2.example.com": Test.random_string(6) + "." + getenv("TEST_DOMAIN2"),
        "app3.example.com": Test.random_string(6) + "." + getenv("TEST_DOMAIN3"),
    }
else:  # swarm
    domains = {
        "www.example.com": Test.random_string(6) + "." + getenv("TEST_DOMAIN1_1"),
        "auth.example.com": Test.random_string(6) + "." + getenv("TEST_DOMAIN1_2"),
        "app1.example.com": Test.random_string(6) + "." + getenv("TEST_DOMAIN1"),
        "app2.example.com": Test.random_string(6) + "." + getenv("TEST_DOMAIN2"),
        "app3.example.com": Test.random_string(6) + "." + getenv("TEST_DOMAIN3"),
    }

for example in glob("./examples/*"):
    if isfile(f"{example}/tests.json"):
        try:
            with open(f"{example}/tests.json") as f:
                tests = loads(f.read())
            if test_type not in tests["kinds"]:
                log(
                    "TESTS",
                    "ℹ️",
                    "Skipping tests for " + tests["name"] + " (not in kinds)",
                )
                continue
            log("TESTS", "ℹ️", f"JSON test = {dumps(tests)}")
            test_obj = None
            no_copy_container = False
            delay = 0
            if "no_copy_container" in tests:
                no_copy_container = tests["no_copy_container"]
            if "delay" in tests:
                delay = tests["delay"]
            if test_type == "docker":
                test_obj = DockerTest(
                    tests["name"],
                    tests["timeout"],
                    tests["tests"],
                    no_copy_container=no_copy_container,
                    delay=delay,
                    domains=domains,
                )
            elif test_type == "autoconf":
                test_obj = AutoconfTest(
                    tests["name"],
                    tests["timeout"],
                    tests["tests"],
                    no_copy_container=no_copy_container,
                    delay=delay,
                    domains=domains,
                )
            elif test_type == "swarm":
                test_obj = SwarmTest(tests["name"], tests["timeout"], tests["tests"], delay=delay, domains=domains)
            elif test_type == "kubernetes":
                test_obj = KubernetesTest(tests["name"], tests["timeout"], tests["tests"], delay=delay, domains=domains)
            elif test_type == "linux":
                test_obj = LinuxTest(tests["name"], tests["timeout"], tests["tests"], distro, domains=domains)
            if not test_obj.run_tests():
                log("TESTS", "❌", "Tests failed for " + tests["name"])
                if test_type == "linux":
                    ret = end_fun(distro)
                else:
                    ret = end_fun()
                _exit(1)
        except:
            log(
                "TESTS",
                "❌",
                "Exception while executing test for example " + example + " : " + format_exc(),
            )
            if test_type == "linux":
                ret = end_fun(distro)
            else:
                ret = end_fun()
            exit(1)

if test_type == "linux":
    ret = end_fun(distro)
else:
    ret = end_fun()
if not ret:
    log("TESTS", "❌", "Test.end() failed")
    exit(1)

log("TESTS", "ℹ️", "All tests finished for " + test_type + " !")

run("docker system prune", shell=True)
