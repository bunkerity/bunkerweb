#!/usr/bin/env python3

from sys import path, argv, exit
from glob import glob
from os import getcwd, _exit
from os.path import isfile
from traceback import format_exc
from json import loads
path.append(getcwd() + "/utils")
path.append(getcwd() + "/tests")

from Test import Test
from DockerTest import DockerTest
from logger import log

if len(argv) != 2 :
    log("TESTS", "❌", "Missing type argument")
    exit(1)

test_type = argv[1]
if not test_type in ["linux", "docker", "autoconf", "swarm", "kubernetes", "ansible"] :
    log("TESTS", "❌", "Wrong type argument " + test_type)
    exit(1)

log("TESTS", "ℹ️", "Starting tests for " + test_type + " ...")
ret = False
end_fun = None
if test_type == "docker" :
    ret = DockerTest.init()
    end_fun = DockerTest.end
if not ret :
    log("TESTS", "❌", "Test.init() failed")
    exit(1)

for example in glob("./examples/*") :
    if isfile(example + "/tests.json") :
        try :
            with open(example + "/tests.json") as f :
                tests = loads(f.read())
            if not test_type in tests["kinds"] :
                log("TESTS", "ℹ️", "Skipping tests for " + tests["name"] + " (not in kinds)")
                continue
            test_obj = None
            if test_type == "docker" :
                test_obj = DockerTest(tests["name"], tests["timeout"], tests["tests"])
            if not test_obj.run_tests() :
                log("TESTS", "❌", "Tests failed for " + tests["name"])
                end_fun()
                _exit(1)
        except :
            log("TESTS", "❌", "Exception while executing test for example " + example + " : " + format_exc())
            end_fun()
            exit(1)

if not end_fun() :
    log("TESTS", "❌", "Test.end() failed")
    exit(1)

log("TESTS", "ℹ️", "All tests finished for " + test_type + " !")