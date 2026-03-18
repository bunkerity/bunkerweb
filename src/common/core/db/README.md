The Database plugin provides a robust database integration for BunkerWeb by enabling centralized storage and management of configuration data, logs, and other essential information.

This core component supports multiple database engines, including SQLite, PostgreSQL, MySQL/MariaDB, and Oracle, allowing you to choose the database solution that best fits your environment and requirements.

**How it works:**

1. BunkerWeb connects to your configured database using the provided URI in the SQLAlchemy format.
2. Critical configuration data, runtime information, and job logs are stored securely in the database.
3. Automatic maintenance processes optimize your database by managing data growth and cleaning up excess records.
4. For high-availability scenarios, you can configure a read-only database URI that serves both as a failover and as a method to offload read operations.
5. Database operations are logged according to your specified log level, providing appropriate visibility into database interactions.

### How to Use

Follow these steps to configure and use the Database feature:

1. **Choose a database engine:** Select from SQLite (default), PostgreSQL, MySQL/MariaDB, or Oracle based on your requirements.
2. **Configure the database URI:** Set the `DATABASE_URI` to connect to your primary database using the SQLAlchemy format.
3. **Optional read-only database:** For high-availability setups, configure a `DATABASE_URI_READONLY` as a fallback or for read operations.

### Configuration Settings

| Setting                  | Default                                   | Context | Multiple | Description                                                                                                           |
| ------------------------ | ----------------------------------------- | ------- | -------- | --------------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URI`                    | `sqlite:////var/lib/bunkerweb/db.sqlite3` | global  | no       | **Database URI:** The primary database connection string in the SQLAlchemy format.                                                                                          |
| `DATABASE_URI_READONLY`           |                                           | global  | no       | **Read-Only Database URI:** Optional database for read-only operations or as a failover if the main database is down.                                                       |
| `DATABASE_LOG_LEVEL`              | `warning`                                 | global  | no       | **Log Level:** The verbosity level for database logs. Options: `debug`, `info`, `warn`, `warning`, or `error`.                                                              |
| `DATABASE_MAX_JOBS_RUNS`          | `10000`                                   | global  | no       | **Maximum Job Runs:** The maximum number of job execution records to retain in the database before automatic cleanup.                                                       |
| `DATABASE_MAX_SESSION_AGE_DAYS`   | `14`                                      | global  | no       | **Session Retention:** The maximum age (in days) for UI user sessions before they are purged automatically.                                                                 |
| `DATABASE_POOL_SIZE`              | `40`                                      | global  | no       | **Pool Size:** The number of connections to keep in the database connection pool.                                                                                            |
| `DATABASE_POOL_MAX_OVERFLOW`      | `20`                                      | global  | no       | **Pool Max Overflow:** The maximum number of connections to create above the pool size. Set to `-1` for unlimited overflow.                                                  |
| `DATABASE_POOL_TIMEOUT`           | `5`                                       | global  | no       | **Pool Timeout:** The number of seconds to wait before giving up on getting a connection from the pool.                                                                      |
| `DATABASE_POOL_RECYCLE`           | `1800`                                    | global  | no       | **Pool Recycle:** The number of seconds after which a connection is automatically recycled. Set to `-1` to disable.                                                          |
| `DATABASE_POOL_PRE_PING`          | `yes`                                     | global  | no       | **Pool Pre-Ping:** Whether to test connections for liveness upon each checkout from the pool.                                                                                |
| `DATABASE_POOL_RESET_ON_RETURN`   |                                           | global  | no       | **Pool Reset on Return:** How connections are reset when returned to the pool. Empty for auto (`none` for MySQL/MariaDB, `rollback` for others). Options: `rollback`, `commit`, `none`. |
| `DATABASE_RETRY_TIMEOUT`          | `60`                                      | global  | no       | **Retry Timeout:** The maximum number of seconds to wait for the database to be available on startup.                                                                        |
| `DATABASE_REQUEST_RETRY_ATTEMPTS` | `2`                                       | global  | no       | **Request Retry Attempts:** The number of retry attempts for transient database errors during operations.                                                                    |
| `DATABASE_REQUEST_RETRY_DELAY`    | `0.25`                                    | global  | no       | **Request Retry Delay:** The delay in seconds between retry attempts for transient database errors.                                                                          |

!!! tip "Database Selection"
    - **SQLite** (default): Ideal for single-node deployments or testing environments due to its simplicity and file-based nature.
    - **PostgreSQL**: Recommended for production environments with multiple BunkerWeb instances due to its robustness and concurrency support.
    - **MySQL/MariaDB**: A good alternative to PostgreSQL with similar production-grade capabilities.
    - **Oracle**: Suitable for enterprise environments where Oracle is already the standard database platform.

!!! info "SQLAlchemy URI Format"
    The database URI follows the SQLAlchemy format:

    - SQLite: `sqlite:////path/to/database.sqlite3`
    - PostgreSQL: `postgresql://username:password@hostname:port/database`
    - MySQL/MariaDB: `mysql://username:password@hostname:port/database` or `mariadb://username:password@hostname:port/database`
    - Oracle: `oracle://username:password@hostname:port/database`

!!! warning "Database Maintenance"
    The plugin automatically runs daily maintenance jobs:

    - **Cleanup Excess Job Runs:** Purges job execution history beyond the `DATABASE_MAX_JOBS_RUNS` limit.
    - **Cleanup Expired UI Sessions:** Removes UI user sessions older than `DATABASE_MAX_SESSION_AGE_DAYS`.

    Together, these jobs prevent unbounded database growth while preserving useful operational history.
