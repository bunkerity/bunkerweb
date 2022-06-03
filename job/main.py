#!/usr/bin/python3

import argparse, sys, re, signal, time, traceback, os

import sys
sys.path.append("/opt/bunkerweb/deps/python")
sys.path.append("/opt/bunkerweb/jobs")
sys.path.append("/opt/bunkerweb/utils")

from dotenv import dotenv_values
from threading import Lock
from logger import log
from JobScheduler import JobScheduler

run = True
scheduler = None
reloading = False

def handle_stop(signum, frame) :
    global run, scheduler
    run = False
    if scheduler is not None :
        scheduler.clear()
    stop(0)
signal.signal(signal.SIGINT, handle_stop)
signal.signal(signal.SIGTERM, handle_stop)

def handle_reload(env) :
    global run, scheduler, reloading
    try :
        if scheduler is not None and run :
            if scheduler.reload(dotenv_values(env)) :
                log("SCHEDULER", "ℹ️", "Reload successful")
            else :
                log("SCHEDULER", "❌", "Reload failed")
        else :
            log("SCHEDULER", "⚠️", "Ignored reload operation because scheduler is not running ...")
    except :
        log("SCHEDULER", "❌", "Exception while reloading scheduler : " + traceback.format_exc())

def handle_reload_bw(signum, frame) :
    handle_reload("/etc/nginx/variables.env")
signal.signal(signal.SIGUSR1, handle_reload_bw)

def handle_reload_api(signum, frame) :
    handle_reload("/opt/bunkerweb/tmp/jobs.env")
signal.signal(signal.SIGUSR2, handle_reload_api)

def stop(status) :
    os.remove("/opt/bunkerweb/tmp/scheduler.pid")
    os._exit(status)

if __name__ == "__main__" :

    try :

        # Don't execute if pid file exists
        if os.path.isfile("/opt/bunkerweb/tmp/scheduler.pid") :
            log("SCHEDULER", "❌", "Scheduler is already running, skipping execution ...")
            os._exit(1)

        # Write pid to file
        with open("/opt/bunkerweb/tmp/scheduler.pid", "w") as f :
            f.write(str(os.getpid()))

        # Parse arguments
        parser = argparse.ArgumentParser(description="Job scheduler for BunkerWeb")
        parser.add_argument("--run", action="store_true", help="only run jobs one time in foreground")
        parser.add_argument("--variables", default="/etc/nginx/variables.env", type=str, help="path to the variables")
        args = parser.parse_args()

        # Read env file
        env = dotenv_values(args.variables)

        # Instantiate scheduler
        scheduler = JobScheduler(env=env)

        # Only run jobs once
        log("SCHEDULER", "ℹ️", "Executing job scheduler ...")
        if args.run :
            ret = scheduler.run_once()
            if not ret :
                log("SCHEDULER", "❌", "At least one job in run_once() failed")
                stop(1)
            else :
                log("SCHEDULER", "ℹ️", "All jobs in run_once() were successful")

        # Or infinite schedule
        else :
            scheduler.setup()
            while run :
                scheduler.run_pending()
                time.sleep(1)

    except :
        log("SCHEDULER", "❌", "Exception while executing scheduler : " + traceback.format_exc())
        stop(1)

    log("SCHEDULER", "ℹ️", "Job scheduler stopped")
    stop(0)
