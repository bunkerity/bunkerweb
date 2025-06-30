#!/usr/bin/env python3

from datetime import datetime
from json import dumps, loads
from os import getenv
from os.path import join, sep
from pathlib import Path
from subprocess import PIPE, run
from sys import exit as sys_exit, path as sys_path
from time import sleep
from typing import Literal
from zipfile import ZIP_DEFLATED, ZipFile

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from sqlalchemy.engine.url import make_url

from common_utils import bytes_hash  # type: ignore
from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from model import Base  # type: ignore

LOGGER = setup_logger("BACKUP")

BACKUP_DIR = Path(getenv("BACKUP_DIRECTORY", "/var/lib/bunkerweb/backups"))
DB_LOCK_FILE = Path(sep, "var", "lib", "bunkerweb", "db.lock")

def debug_log(logger, message):
    # Log debug messages only when LOG_LEVEL environment variable is set to
    # "debug"
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] {message}")


def acquire_db_lock():
    # Acquire the database lock to prevent concurrent access to the database
    current_time = datetime.now().astimezone()
    
    debug_log(LOGGER, f"Attempting to acquire database lock at {current_time}")
    debug_log(LOGGER, f"Lock file path: {DB_LOCK_FILE}")
    
    while (DB_LOCK_FILE.is_file() and 
           DB_LOCK_FILE.stat().st_ctime + 30 > current_time.timestamp()):
        LOGGER.warning(
            "Database is locked, waiting for it to be unlocked "
            "(timeout: 30s) ..."
        )
        debug_log(LOGGER, f"Lock file exists, waiting... Current time: "
                 f"{current_time.timestamp()}, Lock time: "
                 f"{DB_LOCK_FILE.stat().st_ctime}")
        sleep(1)
    
    DB_LOCK_FILE.unlink(missing_ok=True)
    DB_LOCK_FILE.touch()
    
    debug_log(LOGGER, "Database lock acquired successfully")


def update_cache_file(db: Database, backup_dir: Path) -> str:
    # Update the cache file in the database with current backup information
    debug_log(LOGGER, f"Updating cache file for backup directory: {backup_dir}")
    
    backup_data = loads(
        db.get_job_cache_file("backup-data", "backup.json") or "{}"
    )
    
    backup_files = sorted([file.name for file in backup_dir.glob("backup-*.zip")])
    backup_data["files"] = backup_files
    backup_data["date"] = datetime.now().astimezone().isoformat()
    
    debug_log(LOGGER, f"Found {len(backup_files)} backup files")
    debug_log(LOGGER, f"Backup files: {backup_files}")
    
    content = dumps(backup_data, indent=2).encode()
    checksum = bytes_hash(content)
    
    err = db.upsert_job_cache(
        None, "backup.json", content, 
        job_name="backup-data", checksum=checksum
    )
    
    if err:
        LOGGER.error(f"Failed to update the backup.json cache file: {err}")
        return err

    LOGGER.info("Backup cache file updated successfully")
    debug_log(LOGGER, f"Cache content checksum: {checksum}")
    
    return ""


def backup_database(current_time: datetime, db: Database = None, 
                   backup_dir: Path = BACKUP_DIR) -> Database:
    # Create a backup of the database with timestamp and compression
    db = db or Database(LOGGER)

    database_url = make_url(db.database_uri)
    database: Literal["sqlite", "mariadb", "mysql", "postgresql", 
                      "oracle"] = database_url.drivername.split("+")[0]
    
    backup_file = backup_dir.joinpath(
        f"backup-{database}-{current_time.strftime('%Y-%m-%d_%H-%M-%S')}.zip"
    )
    
    debug_log(LOGGER, f"Database type: {database}")
    debug_log(LOGGER, f"Database URL: {database_url}")
    debug_log(LOGGER, f"Backup file path: {backup_file}")
    
    stderr = "Table 'db.test_"
    start_time = datetime.now().astimezone()

    # Get table names from the SQLAlchemy model
    model_tables = list(Base.metadata.tables.keys())
    LOGGER.info(f"Backing up {len(model_tables)} tables defined in the model")
    
    debug_log(LOGGER, f"Tables to backup: {model_tables}")

    while ("Table 'db.test_" in stderr and 
           (datetime.now().astimezone() - start_time).total_seconds() < 10):
        
        if database == "sqlite":
            db_path = Path(database_url.database)
            
            debug_log(LOGGER, f"SQLite database path: {db_path}")

            LOGGER.info("Creating a backup for the SQLite database ...")

            # For SQLite, use a different approach to dump only specific tables
            dump_commands = "\n".join([f".dump {table}" 
                                     for table in model_tables])
            
            debug_log(LOGGER, f"SQLite dump commands: {dump_commands}")
            
            proc = run(
                ["sqlite3", db_path.as_posix()],
                input=dump_commands.encode(),
                stdout=PIPE,
                stderr=PIPE,
                env={"PATH": getenv("PATH", ""), 
                     "PYTHONPATH": getenv("PYTHONPATH", "")},
            )
        else:
            url = make_url(db.database_uri)
            db_user = url.username or ""
            db_password = url.password or ""
            db_host = url.host or ""
            db_port = str(url.port) if url.port else ""
            db_database_name = url.database or ""
            db_query_args = url.query if hasattr(url, "query") else {}
            
            debug_log(LOGGER, f"Database connection details - Host: {db_host}, "
                     f"Port: {db_port}, Database: {db_database_name}, "
                     f"User: {db_user}")
            debug_log(LOGGER, f"Query args: {db_query_args}")

            if database in ("mariadb", "mysql"):
                LOGGER.info("Creating a backup for the MariaDB/MySQL database ...")

                cmd = [
                    "mysqldump" if database == "mysql" else "mariadb-dump", 
                    "-h", db_host, "-u", db_user, db_database_name
                ]
                
                if db_port:
                    cmd.extend(["-P", db_port])

                # Add options to handle large data and improve compatibility
                cmd.extend([
                    "--single-transaction",  # Consistent backup for InnoDB
                    "--routines",  # Include stored procedures and functions
                    "--triggers",  # Include triggers
                    "--max_allowed_packet=2147483648",  # 2GB max packet size
                    "--quick",  # Retrieve rows one at a time
                    "--lock-tables=false",  # Don't lock tables
                    "--skip-add-locks",  # Don't add LOCK TABLES statements
                    "--default-character-set=utf8mb4",  # Use utf8mb4 charset
                ])

                # Apply additional arguments from query parameters
                for key, value in db_query_args.items():
                    if key == "ssl" and value == "true":
                        cmd.append("--ssl")
                    elif key == "charset":
                        cmd.extend(["--default-character-set", value])

                # Add specific tables to backup
                cmd.extend(model_tables)
                
                debug_log(LOGGER, f"MySQL/MariaDB dump command: {' '.join(cmd)}")

                proc = run(
                    cmd,
                    stdout=PIPE,
                    stderr=PIPE,
                    env={"MYSQL_PWD": db_password, 
                         "PATH": getenv("PATH", ""), 
                         "PYTHONPATH": getenv("PYTHONPATH", "")},
                )
                
            elif database == "postgresql":
                LOGGER.info("Creating a backup for the PostgreSQL database ...")

                cmd = [
                    "pg_dump", "-h", db_host, "-U", db_user, 
                    db_database_name, "-w", "--no-password"
                ]
                
                if db_port:
                    cmd.extend(["-p", db_port])

                # Add options to handle large data and improve compatibility
                cmd.extend([
                    "--no-owner",  # Skip ownership commands
                    "--no-privileges",  # Skip privilege commands
                    "--format=plain",  # Plain text format
                    "--verbose",  # Verbose output for debugging
                ])

                # Apply additional arguments from query parameters
                pg_env = {"PGPASSWORD": db_password}
                for key, value in db_query_args.items():
                    if key == "sslmode":
                        pg_env["PGSSLMODE"] = value
                    elif key == "sslrootcert":
                        pg_env["PGSSLROOTCERT"] = value

                # Add specific tables to backup
                for table in model_tables:
                    cmd.extend(["-t", table])
                
                debug_log(LOGGER, f"PostgreSQL dump command: {' '.join(cmd)}")
                debug_log(LOGGER, f"PostgreSQL environment: {pg_env}")

                proc = run(
                    cmd, 
                    stdout=PIPE, 
                    stderr=PIPE, 
                    env={"PATH": getenv("PATH", ""), 
                         "PYTHONPATH": getenv("PYTHONPATH", "")} | pg_env
                )
                
            elif database == "oracle":
                LOGGER.warning(
                    "Creating a database backup for Oracle is not supported"
                )
                return db

        stderr = (proc.stderr.decode() 
                 if hasattr(proc, "stderr") and proc.stderr else "")
        
        debug_log(LOGGER, f"Process return code: {proc.returncode}")
        debug_log(LOGGER, f"Process stderr: {stderr}")
        if proc.stdout:
            debug_log(LOGGER, f"Process stdout length: {len(proc.stdout)}")
        
        if "Table 'db.test_" not in stderr and proc.returncode != 0:
            LOGGER.error(f"Failed to dump the database: {stderr}")
            sys_exit(1)

    if (datetime.now().astimezone() - start_time).total_seconds() >= 10:
        LOGGER.error("Failed to dump the database: Timeout reached")
        sys_exit(1)

    # Create compressed backup file
    debug_log(LOGGER, f"Creating compressed backup file: {backup_file}")
    debug_log(LOGGER, f"Backup data size: {len(proc.stdout)} bytes")
    
    with ZipFile(backup_file, "w", compression=ZIP_DEFLATED) as zipf:
        zipf.writestr(backup_file.with_suffix(".sql").name, proc.stdout)

    backup_file.chmod(0o600)

    LOGGER.info(
        f"💾 Backup {backup_file.name} created successfully in {backup_dir}"
    )
    
    debug_log(LOGGER, f"Backup file size: {backup_file.stat().st_size} bytes")
    debug_log(LOGGER, f"Backup file permissions: {oct(backup_file.stat().st_mode)}")
    
    return db


def restore_database(backup_file: Path, db: Database = None) -> Database:
    # Restore the database from a compressed backup file
    db = db or Database(LOGGER)
    
    debug_log(LOGGER, f"Starting database restore from: {backup_file}")
    debug_log(LOGGER, f"Backup file exists: {backup_file.exists()}")
    debug_log(LOGGER, f"Backup file size: {backup_file.stat().st_size} bytes")
    
    # Drop all existing tables
    Base.metadata.drop_all(db.sql_engine)
    
    database_url = make_url(db.database_uri)
    database: Literal["sqlite", "mariadb", "mysql", "postgresql", 
                      "oracle"] = database_url.drivername.split("+")[0]
    
    debug_log(LOGGER, f"Database type for restore: {database}")

    if database == "sqlite":
        db_path = Path(database_url.database)
        
        debug_log(LOGGER, f"SQLite database path: {db_path}")

        # Clear the database
        proc = run(
            ["sqlite3", db_path.as_posix(), ".read", "/dev/null"],
            stdout=PIPE,
            stderr=PIPE,
            env={"PATH": getenv("PATH", ""), 
                 "PYTHONPATH": getenv("PYTHONPATH", "")},
        )

        LOGGER.info("Restoring the SQLite database ...")

        tmp_file = Path(
            sep, "var", "tmp", "bunkerweb", 
            backup_file.with_suffix(".sql").name
        )
        
        debug_log(LOGGER, f"Temporary SQL file: {tmp_file}")
        
        with ZipFile(backup_file, "r") as zipf:
            zipf.extractall(path=tmp_file.parent)

        proc = run(
            ["sqlite3", db_path.as_posix(), f".read {tmp_file.as_posix()}"],
            stdout=PIPE,
            stderr=PIPE,
            env={"PATH": getenv("PATH", ""), 
                 "PYTHONPATH": getenv("PYTHONPATH", "")},
        )
        tmp_file.unlink(missing_ok=True)
        
    else:
        url = make_url(db.database_uri)
        db_user = url.username or ""
        db_password = url.password or ""
        db_host = url.host or ""
        db_port = str(url.port) if url.port else ""
        db_database_name = url.database or ""
        db_query_args = url.query if hasattr(url, "query") else {}
        
        debug_log(LOGGER, f"Database connection details - Host: {db_host}, "
                 f"Port: {db_port}, Database: {db_database_name}, "
                 f"User: {db_user}")

        if database in ("mariadb", "mysql"):
            LOGGER.info("Restoring the MariaDB/MySQL database ...")

            cmd = ["mysql", "-h", db_host, "-u", db_user, db_database_name]
            if db_port:
                cmd.extend(["-P", db_port])

            # Apply additional arguments from query parameters
            for key, value in db_query_args.items():
                if key == "ssl" and value == "true":
                    cmd.append("--ssl")
                elif key == "charset":
                    cmd.extend(["--default-character-set", value])
            
            debug_log(LOGGER, f"MySQL/MariaDB restore command: {' '.join(cmd)}")

            with ZipFile(backup_file, "r") as zipf:
                sql_content = zipf.read(backup_file.with_suffix(".sql").name)
                
                debug_log(LOGGER, f"SQL content size: {len(sql_content)} bytes")
                
                proc = run(
                    cmd,
                    stdout=PIPE,
                    stderr=PIPE,
                    env={"PATH": getenv("PATH", ""), 
                         "PYTHONPATH": getenv("PYTHONPATH", ""), 
                         "MYSQL_PWD": db_password},
                    input=sql_content,
                )
                
        elif database == "postgresql":
            LOGGER.info("Restoring the PostgreSQL database ...")

            cmd = ["psql", "-h", db_host, "-U", db_user, db_database_name]
            if db_port:
                cmd.extend(["-p", db_port])

            # Apply additional arguments from query parameters
            pg_env = {"PGPASSWORD": db_password}
            for key, value in db_query_args.items():
                if key == "sslmode":
                    pg_env["PGSSLMODE"] = value
                elif key == "sslrootcert":
                    pg_env["PGSSLROOTCERT"] = value
            
            debug_log(LOGGER, f"PostgreSQL restore command: {' '.join(cmd)}")
            debug_log(LOGGER, f"PostgreSQL environment: {pg_env}")

            with ZipFile(backup_file, "r") as zipf:
                sql_content = zipf.read(backup_file.with_suffix(".sql").name)
                
                debug_log(LOGGER, f"SQL content size: {len(sql_content)} bytes")
                
                proc = run(
                    cmd,
                    stdout=PIPE,
                    stderr=PIPE,
                    input=sql_content,
                    env={"PATH": getenv("PATH", ""), 
                         "PYTHONPATH": getenv("PYTHONPATH", "")} | pg_env,
                )
                
        elif database == "oracle":
            LOGGER.warning(
                "Restoring a database backup for Oracle is not supported"
            )
            return db

    debug_log(LOGGER, f"Restore process return code: {proc.returncode}")
    if proc.stderr:
        debug_log(LOGGER, f"Restore process stderr: {proc.stderr.decode()}")

    if proc.returncode != 0:
        LOGGER.error(f"Failed to restore the database: {proc.stderr.decode()}")
        sys_exit(1)

    # Apply database changes after restore
    err = db.checked_changes(plugins_changes="all", value=True)
    if err:
        LOGGER.error(
            f"Error while applying changes to the database: {err}, "
            f"you may need to reload the application"
        )

    LOGGER.info(f"💾 Database restored successfully from {backup_file}")
    
    debug_log(LOGGER, "Database restore completed successfully")
    
    return db