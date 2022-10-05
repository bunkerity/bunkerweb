#!/usr/bin/env python3

import argparse, os, sys, shutil, glob, traceback, json

sys.path.append("/opt/bunkerweb/deps/python")
sys.path.append("/opt/bunkerweb/gen")
sys.path.append("/opt/bunkerweb/utils")

from logger import log

from Configurator import Configurator
from Templator import Templator

if __name__ == "__main__" :

    try :

        # Parse arguments
        parser = argparse.ArgumentParser(description="BunkerWeb config generator")
        parser.add_argument("--settings", default="/opt/bunkerweb/settings.json", type=str, help="file containing the main settings")
        parser.add_argument("--templates", default="/opt/bunkerweb/confs", type=str, help="directory containing the main template files")
        parser.add_argument("--core", default="/opt/bunkerweb/core", type=str, help="directory containing the core plugins")
        parser.add_argument("--plugins", default="/opt/bunkerweb/plugins", type=str, help="directory containing the external plugins")
        parser.add_argument("--output", default="/etc/nginx", type=str, help="where to write the rendered files")
        parser.add_argument("--target", default="/etc/nginx", type=str, help="where nginx will search for configurations files")
        parser.add_argument("--variables", default="/opt/bunkerweb/variables.env", type=str, help="path to the file containing environment variables")
        args = parser.parse_args()

        log("GENERATOR", "ℹ️", "Generator started ...")
        log("GENERATOR", "ℹ️", "Settings : " + args.settings)
        log("GENERATOR", "ℹ️", "Templates : " + args.templates)
        log("GENERATOR", "ℹ️", "Core : " + args.core)
        log("GENERATOR", "ℹ️", "Plugins : " + args.plugins)
        log("GENERATOR", "ℹ️", "Output : " + args.output)
        log("GENERATOR", "ℹ️", "Target : " + args.target)
        log("GENERATOR", "ℹ️", "Variables : " + args.variables)

        # Check existences and permissions
        log("GENERATOR", "ℹ️", "Checking arguments ...")
        files = [args.settings, args.variables]
        paths_rx = [args.core, args.plugins, args.templates]
        paths_rwx = [args.output]
        for file in files :
            if not os.path.exists(file) :
                log("GENERATOR", "❌", "Missing file : " + file)
                sys.exit(1)
            if not os.access(file, os.R_OK) :
                log("GENERATOR", "❌", "Can't read file : " + file)
                sys.exit(1)
        for path in paths_rx + paths_rwx :
            if not os.path.isdir(path) :
                log("GENERATOR", "❌", "Missing directory : " + path)
                sys.exit(1)
            if not os.access(path, os.R_OK | os.X_OK) :
                log("GENERATOR", "❌", "Missing RX rights on directory : " + path)
                sys.exit(1)
        for path in paths_rwx :
            if not os.access(path, os.W_OK) :
                log("GENERATOR", "❌", "Missing W rights on directory : " + path)
                sys.exit(1)

        # Check core plugins orders
        log("GENERATOR", "ℹ️", "Checking core plugins orders ...")
        core_plugins = {}
        files = glob.glob(args.core + "/*/plugin.json")
        for file in files :
            try :
                with open(file) as f :
                    core_plugin = json.loads(f.read())
                    
                    if core_plugin["order"] not in core_plugins :
                        core_plugins[core_plugin["order"]] = []
                    
                    core_plugins[core_plugin["order"]].append({"id": core_plugin["id"], "settings": core_plugin["settings"]})
            except :
                log("GENERATOR", "❌", "Exception while loading JSON from " + file + " :")
                print(traceback.format_exc())

        core_settings = {}
        for order in core_plugins :
            if len(core_plugins[order]) > 1 and order != 999 :
                log("GENERATOR", "⚠️", "Multiple plugins have the same order (" + str(order) + ") : " + ", ".join(plugin["id"] for plugin in core_plugins[order]) + ". Therefor, the execution order will be random.")
            
            for plugin in core_plugins[order] :
                core_settings.update(plugin["settings"])

        # Compute the config
        log("GENERATOR", "ℹ️", "Computing config ...")
        configurator = Configurator(args.settings, core_settings, args.plugins, args.variables)
        config = configurator.get_config()

        # Remove old files
        log("GENERATOR", "ℹ️", "Removing old files ...")
        files = glob.glob(args.output + "/*")
        for file in files :
            if os.path.islink(file) :
                os.unlink(file)
            elif os.path.isfile(file) :
                os.remove(file)
            elif os.path.isdir(file) :
                shutil.rmtree(file, ignore_errors=False)

        # Render the templates
        log("GENERATOR", "ℹ️", "Rendering templates ...")
        templator = Templator(args.templates, args.core, args.plugins, args.output, args.target, config)
        templator.render()

        # We're done
        log("GENERATOR", "ℹ️", "Generator successfully executed !")
        sys.exit(0)

    except SystemExit as e :
        sys.exit(e)
    except :
        log("GENERATOR", "❌", "Exception while executing generator : " + traceback.format_exc())
        sys.exit(1)
