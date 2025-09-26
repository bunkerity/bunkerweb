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
| `DATABASE_URI`           | `sqlite:////var/lib/bunkerweb/db.sqlite3` | global  | no       | **Database URI:** The primary database connection string in the SQLAlchemy format.                                    |
| `DATABASE_URI_READONLY`  |                                           | global  | no       | **Read-Only Database URI:** Optional database for read-only operations or as a failover if the main database is down. |
| `DATABASE_LOG_LEVEL`     | `warning`                                 | global  | no       | **Log Level:** The verbosity level for database logs. Options: `debug`, `info`, `warn`, `warning`, or `error`.        |
| `DATABASE_MAX_JOBS_RUNS` | `10000`                                   | global  | no       | **Maximum Job Runs:** The maximum number of job execution records to retain in the database before automatic cleanup. |
| `DATABASE_MAX_SESSION_AGE_DAYS` | `14`                              | global  | no       | **Session Retention:** The maximum age (in days) for UI user sessions before they are purged automatically.           |

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
