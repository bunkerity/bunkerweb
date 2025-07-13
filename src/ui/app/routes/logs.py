from contextlib import suppress
from os import listdir
from os.path import isabs, sep, join
from pathlib import Path
import json
import time
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="UI-logs",
    log_file_path="/var/log/bunkerweb/ui.log"
)

logger.debug("Debug mode enabled for UI-logs")

from flask import Blueprint, Response, render_template, request
from flask_login import login_required
from werkzeug.utils import secure_filename

from app.routes.utils import error_message


logs = Blueprint("logs", __name__)


@logs.route("/logs", methods=["GET"])
@login_required
def logs_page():
    logger.debug("logs_page() called")
    logs_path = Path(sep, "var", "log", "bunkerweb")
    letsencrypt_path = logs_path / "letsencrypt"

    files = {"main": [], "letsencrypt": []}

    # Get main log files
    if logs_path.is_dir() and listdir(logs_path):
        main_log_files = [file.name for file in logs_path.glob("*.log") if file.is_file()]
        files["main"].extend(main_log_files)
        logger.debug(f"Found {len(main_log_files)} main log files: {main_log_files}")
    else:
        logger.debug("No main log directory or files found")

    if letsencrypt_path.is_dir() and listdir(letsencrypt_path):
        letsencrypt_files = [file.name for file in letsencrypt_path.glob("*.log*") if file.is_file()]

        # Sort letsencrypt files with proper numerical ordering
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
        
        logger.debug(f"Found {len(letsencrypt_files)} letsencrypt log files: {letsencrypt_files}")
    else:
        logger.debug("No letsencrypt log directory or files found")

    # Flatten files for compatibility with existing logic
    all_files = files["main"] + files["letsencrypt"]
    logger.debug(f"Total log files available: {len(all_files)}")

    current_file = secure_filename(request.args.get("file", ""))
    page = request.args.get("page", 0)

    if current_file and current_file not in all_files:
        logger.debug(f"Requested file not found: {current_file}")
        return Response("No such file", 404)

    if isabs(current_file) or ".." in current_file:
        logger.debug(f"Invalid file path requested: {current_file}")
        return error_message("Invalid file path", 400)

    raw_logs = (
        "Select a log file to view its contents"
        if all_files
        else "There are no log files to display, check the documentation for more information on how to enable logging"
    )
    page_num = 1
    
    if current_file:
        logger.debug(f"Loading log file: {current_file}, page: {page}")
        
        if current_file.startswith("letsencrypt_"):
            file_path = logs_path.joinpath(current_file.replace("letsencrypt_", "letsencrypt/"))
        else:
            file_path = logs_path.joinpath(current_file)

        try:
            with file_path.open(encoding="utf-8", errors="replace") as f:
                raw_logs = f.read().splitlines()
                total_lines = len(raw_logs)
                page_num = total_lines // 10000 + 1
                
                if not page:
                    page = page_num
                
                start_line = int(page) * 10000 - 10000
                end_line = int(page) * 10000
                raw_logs = "\n".join(raw_logs[start_line:end_line])
                
                logger.debug(f"Loaded {total_lines} lines from {current_file}, "
                           f"showing page {page}/{page_num} (lines {start_line}-{end_line})")
        except Exception as e:
            logger.exception(f"Error reading log file {current_file}: {e}")
            raw_logs = f"Error reading log file: {e}"

    return render_template("logs.html", logs=raw_logs, files=files, current_file=current_file, current_page=int(page) or page_num, page_num=page_num)


@logs.route("/logs/stream", methods=["GET"])
@login_required
def stream_logs():
    logger.debug("stream_logs() called")
    logs_path = Path(sep, "var", "log", "bunkerweb")

    requested_file = request.args.get("file", "")

    # Handle letsencrypt files with underscore prefix (as used in main route)
    if requested_file.startswith("letsencrypt_"):
        filename_part = requested_file.replace("letsencrypt_", "")
        current_file = f"letsencrypt_{secure_filename(filename_part)}"
        file_path = logs_path.joinpath("letsencrypt", secure_filename(filename_part))
    else:
        current_file = secure_filename(requested_file)
        file_path = logs_path.joinpath(current_file)

    logger.debug(f"Starting log stream for file: {current_file}")

    if not current_file:
        logger.debug("No file specified for streaming")
        return Response("No file specified", 400)

    if isabs(requested_file) or ".." in requested_file:
        logger.debug(f"Invalid file path for streaming: {requested_file}")
        return Response("Invalid file path", 400)

    if not file_path.exists():
        logger.debug(f"File not found for streaming: {file_path}")
        return Response("File not found", 404)

    # Generate real-time log stream with file monitoring and rotation detection.
    # Handles file growth, rotation, and sends periodic heartbeats to maintain connection.
    def generate():
        logger.debug(f"Starting log stream generator for {current_file}")
        last_size = 0
        last_mtime = 0
        heartbeat_counter = 0

        try:
            # Send initial file content to ensure we're up to date
            with file_path.open(encoding="utf-8", errors="replace") as f:
                initial_content = f.read()
            initial_size = file_path.stat().st_size
            logger.debug(f"Initial file size: {initial_size} bytes")
            yield f"data: {json.dumps({'type': 'refresh', 'content': initial_content, 'size': initial_size})}\n\n"
            last_size = initial_size
            last_mtime = file_path.stat().st_mtime

            while True:
                content_sent = False

                try:
                    current_stat = file_path.stat()
                    current_size = current_stat.st_size
                    current_mtime = current_stat.st_mtime

                    # Check if file was modified
                    if current_mtime != last_mtime or current_size != last_size:
                        # File was rotated (new file, smaller size)
                        if current_size < last_size:
                            logger.debug(f"File rotation detected: {last_size} -> {current_size} bytes")
                            with file_path.open(encoding="utf-8", errors="replace") as f:
                                content = f.read()
                            yield f"data: {json.dumps({'type': 'rotated', 'content': content, 'size': current_size})}\n\n"
                            last_size = current_size
                            content_sent = True

                        # File grew (new content)
                        elif current_size > last_size:
                            bytes_added = current_size - last_size
                            logger.debug(f"New content detected: {bytes_added} bytes added")
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
                        yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                        heartbeat_counter = 0

                except FileNotFoundError:
                    logger.debug(f"File was deleted during streaming: {file_path}")
                    yield f"data: {json.dumps({'type': 'error', 'message': 'File was deleted'})}\n\n"
                    break
                except Exception as e:
                    logger.exception(f"Error during log streaming: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                    break

                time.sleep(1)  # Check every second

        except Exception as e:
            logger.exception(f"Critical error in log stream generator: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
