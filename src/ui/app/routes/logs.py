from contextlib import suppress
from os import listdir, getenv, sep
from os.path import isabs, join
from pathlib import Path
from sys import path as sys_path
import json
import time

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for logs module")

from flask import Blueprint, Response, render_template, request
from flask_login import login_required
from werkzeug.utils import secure_filename

from app.routes.utils import error_message


logs = Blueprint("logs", __name__)


# Display log viewer interface with file discovery and pagination.
# Scans BunkerWeb log directories and renders log content with file selection.
@logs.route("/logs", methods=["GET"])
@login_required
def logs_page():
    if DEBUG_MODE:
        logger.debug("logs_page() called")
    
    logs_path = Path(sep, "var", "log", "bunkerweb")
    letsencrypt_path = logs_path / "letsencrypt"
    
    if DEBUG_MODE:
        logger.debug(f"Scanning log directories - main: {logs_path}, letsencrypt: {letsencrypt_path}")

    files = {"main": [], "letsencrypt": []}

    # Get main log files
    if logs_path.is_dir() and listdir(logs_path):
        if DEBUG_MODE:
            logger.debug("Scanning main log directory for .log files")
        
        for file in logs_path.glob("*.log"):
            if file.is_file():
                files["main"].append(file.name)
                
        if DEBUG_MODE:
            logger.debug(f"Found {len(files['main'])} main log files")

    if letsencrypt_path.is_dir() and listdir(letsencrypt_path):
        if DEBUG_MODE:
            logger.debug("Scanning letsencrypt log directory")
        
        letsencrypt_files = [file.name for file in letsencrypt_path.glob("*.log*") if file.is_file()]

        # Sort letsencrypt files with proper numerical ordering for rotated logs.
        # Prioritizes current .log files over rotated .log.X files with numeric sorting.
        def sort_key(filename):
            if filename.endswith(".log"):
                return (0, filename)  # Files ending with .log come first
            else:
                # Extract number from .log.X format
                with suppress(ValueError, IndexError):
                    parts = filename.split(".log.")
                    if len(parts) == 2:
                        return (int(parts[1]), filename)
                return (999999, filename)  # Fallback for unexpected formats

        letsencrypt_files.sort(key=sort_key)
        for file in letsencrypt_files:
            files["letsencrypt"].append(f"letsencrypt_{file}")
            
        if DEBUG_MODE:
            logger.debug(f"Found {len(files['letsencrypt'])} letsencrypt log files")

    # Flatten files for compatibility with existing logic
    all_files = files["main"] + files["letsencrypt"]
    
    if DEBUG_MODE:
        logger.debug(f"Total log files available: {len(all_files)}")

    current_file = secure_filename(request.args.get("file", ""))
    page = request.args.get("page", 0)
    
    if DEBUG_MODE:
        logger.debug(f"Request parameters - file: '{current_file}', page: {page}")

    if current_file and current_file not in all_files:
        if DEBUG_MODE:
            logger.debug(f"Requested file not found in available files: {current_file}")
        return Response("No such file", 404)

    if isabs(current_file) or ".." in current_file:
        if DEBUG_MODE:
            logger.debug(f"Invalid file path detected: {current_file}")
        return error_message("Invalid file path", 400)

    raw_logs = (
        "Select a log file to view its contents"
        if all_files
        else "There are no log files to display, check the documentation for more information on how to enable logging"
    )
    page_num = 1
    
    if current_file:
        if DEBUG_MODE:
            logger.debug(f"Processing log file content for: {current_file}")
        
        if current_file.startswith("letsencrypt_"):
            file_path = logs_path.joinpath(current_file.replace("letsencrypt_", "letsencrypt/"))
        else:
            file_path = logs_path.joinpath(current_file)
            
        if DEBUG_MODE:
            logger.debug(f"Reading log file from path: {file_path}")

        try:
            with file_path.open(encoding="utf-8", errors="replace") as f:
                raw_logs = f.read().splitlines()
                page_num = len(raw_logs) // 10000 + 1
                if not page:
                    page = page_num
                
                if DEBUG_MODE:
                    logger.debug(f"Log file stats - total lines: {len(raw_logs)}, pages: {page_num}, current page: {page}")
                
                raw_logs = "\n".join(raw_logs[int(page) * 10000 - 10000 : int(page) * 10000])  # noqa: E203
                
                if DEBUG_MODE:
                    logger.debug(f"Extracted page content - characters: {len(raw_logs)}")
        except Exception as e:
            logger.exception("Error reading log file")
            if DEBUG_MODE:
                logger.debug(f"Failed to read log file {file_path}: {e}")
            raw_logs = f"Error reading log file: {e}"

    if DEBUG_MODE:
        logger.debug("Rendering logs.html template")

    return render_template("logs.html", logs=raw_logs, files=files, current_file=current_file, current_page=int(page) or page_num, page_num=page_num)


# Provide real-time log streaming via Server-Sent Events with file monitoring.
# Watches log files for changes and streams updates with rotation detection.
@logs.route("/logs/stream", methods=["GET"])
@login_required
def stream_logs():
    if DEBUG_MODE:
        logger.debug("stream_logs() called")
    
    logs_path = Path(sep, "var", "log", "bunkerweb")
    requested_file = request.args.get("file", "")
    
    if DEBUG_MODE:
        logger.debug(f"Stream requested for file: '{requested_file}'")

    # Handle letsencrypt files with underscore prefix (as used in main route)
    if requested_file.startswith("letsencrypt_"):
        filename_part = requested_file.replace("letsencrypt_", "")
        current_file = f"letsencrypt_{secure_filename(filename_part)}"
        file_path = logs_path.joinpath("letsencrypt", secure_filename(filename_part))
    else:
        current_file = secure_filename(requested_file)
        file_path = logs_path.joinpath(current_file)
        
    if DEBUG_MODE:
        logger.debug(f"Resolved file path for streaming: {file_path}")

    if not current_file:
        if DEBUG_MODE:
            logger.debug("No file specified for streaming")
        return Response("No file specified", 400)

    if isabs(requested_file) or ".." in requested_file:
        if DEBUG_MODE:
            logger.debug(f"Invalid file path for streaming: {requested_file}")
        return Response("Invalid file path", 400)

    if not file_path.exists():
        if DEBUG_MODE:
            logger.debug(f"Streaming file not found: {file_path}")
        return Response("File not found", 404)

    # Generate real-time log content stream with file change detection.
    # Monitors file modifications, rotations, and provides heartbeat signals.
    def generate():
        if DEBUG_MODE:
            logger.debug("Starting log stream generator")
        
        last_size = 0
        last_mtime = 0
        heartbeat_counter = 0

        try:
            # Send initial file content to ensure we're up to date
            if DEBUG_MODE:
                logger.debug("Sending initial file content")
            
            with file_path.open(encoding="utf-8", errors="replace") as f:
                initial_content = f.read()
            initial_size = file_path.stat().st_size
            yield f"data: {json.dumps({'type': 'refresh', 'content': initial_content, 'size': initial_size})}\n\n"
            last_size = initial_size
            last_mtime = file_path.stat().st_mtime
            
            if DEBUG_MODE:
                logger.debug(f"Initial content sent - size: {initial_size} bytes")

            while True:
                content_sent = False

                try:
                    current_stat = file_path.stat()
                    current_size = current_stat.st_size
                    current_mtime = current_stat.st_mtime

                    # Check if file was modified
                    if current_mtime != last_mtime or current_size != last_size:
                        if DEBUG_MODE:
                            logger.debug(f"File change detected - size: {current_size}, mtime: {current_mtime}")
                        
                        # File was rotated (new file, smaller size)
                        if current_size < last_size:
                            if DEBUG_MODE:
                                logger.debug("Log rotation detected - sending full content")
                            
                            with file_path.open(encoding="utf-8", errors="replace") as f:
                                content = f.read()
                            yield f"data: {json.dumps({'type': 'rotated', 'content': content, 'size': current_size})}\n\n"
                            last_size = current_size
                            content_sent = True

                        # File grew (new content)
                        elif current_size > last_size:
                            if DEBUG_MODE:
                                logger.debug(f"New content detected - reading from offset {last_size}")
                            
                            with file_path.open(encoding="utf-8", errors="replace") as f:
                                f.seek(last_size)
                                new_content = f.read()
                            yield f"data: {json.dumps({'type': 'append', 'content': new_content, 'size': current_size})}\n\n"
                            last_size = current_size
                            content_sent = True

                        last_mtime = current_mtime
                        heartbeat_counter = 0  # Reset heartbeat counter when content is sent

                    # Send heartbeat every 10 seconds (10 iterations of 1 second sleep)
                    heartbeat_counter += 1
                    if heartbeat_counter >= 10 and not content_sent:
                        if DEBUG_MODE:
                            logger.debug("Sending heartbeat signal")
                        yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                        heartbeat_counter = 0

                except FileNotFoundError:
                    if DEBUG_MODE:
                        logger.debug("Streaming file was deleted")
                    yield f"data: {json.dumps({'type': 'error', 'message': 'File was deleted'})}\n\n"
                    break
                except Exception as e:
                    logger.exception("Error in log streaming")
                    if DEBUG_MODE:
                        logger.debug(f"Stream error: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                    break

                time.sleep(1)  # Check every second

        except Exception as e:
            logger.exception("Fatal error in log stream generator")
            if DEBUG_MODE:
                logger.debug(f"Generator error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    if DEBUG_MODE:
        logger.debug("Starting Server-Sent Events response")

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
