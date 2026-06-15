#!/usr/bin/env python3
from datetime import datetime
from sys import argv
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import delete, func, select

from model import Jobs, Jobs_cache, Jobs_runs  # type: ignore

from .common import DatabaseMixinBase


class DatabaseJobsMixin(DatabaseMixinBase):
    """Job runs and job cache management."""

    def add_job_run(self, job_name: str, success: bool, start_date: datetime, end_date: Optional[datetime] = None) -> str:
        """Add a job run."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            session.add(Jobs_runs(job_name=job_name, success=success, start_date=start_date, end_date=end_date or datetime.now().astimezone()))

            try:
                session.commit()
            except BaseException as e:
                return str(e)
        return ""

    def cleanup_jobs_runs_excess(self, max_runs: int) -> str:
        """Remove excess jobs runs."""
        result = 0
        with self._db_session() as session:
            rows_count = session.scalar(select(func.count()).select_from(Jobs_runs))
            if rows_count > max_runs:
                records_to_delete = session.execute(select(Jobs_runs.id).order_by(Jobs_runs.end_date.asc()).limit(rows_count - max_runs)).all()
                ids_to_delete = [record.id for record in records_to_delete]
                if ids_to_delete:
                    result = session.execute(
                        delete(Jobs_runs).where(Jobs_runs.id.in_(ids_to_delete)), execution_options={"synchronize_session": False}
                    ).rowcount

                try:
                    session.commit()
                except BaseException as e:
                    return str(e)
        return f"Removed {result} excess jobs runs"

    def delete_job_cache(self, file_name: str, *, job_name: Optional[str] = None, service_id: Optional[str] = None) -> str:
        job_name = job_name or argv[0].replace(".py", "")
        filters = {"file_name": file_name, "service_id": service_id or None}
        if job_name:
            filters["job_name"] = job_name

        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            session.execute(delete(Jobs_cache).filter_by(**filters), execution_options={"synchronize_session": False})

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def upsert_job_cache(
        self,
        service_id: Optional[str],
        file_name: str,
        data: bytes,
        *,
        job_name: Optional[str] = None,
        checksum: Optional[str] = None,
    ) -> str:
        """Update the plugin cache in the database"""
        job_name = job_name or argv[0].replace(".py", "")
        service_id = service_id or None
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            cache = session.scalars(select(Jobs_cache).filter_by(job_name=job_name, service_id=service_id, file_name=file_name).limit(1)).first()

            if not cache:
                session.add(
                    Jobs_cache(
                        job_name=job_name,
                        service_id=service_id,
                        file_name=file_name,
                        data=data,
                        last_update=datetime.now().astimezone(),
                        checksum=checksum,
                    )
                )
            else:
                if checksum is None or cache.checksum != checksum:
                    cache.data = data
                    cache.last_update = datetime.now().astimezone()
                    cache.checksum = checksum
                else:
                    # Data unchanged — refresh timestamp to reset expiry window
                    cache.last_update = datetime.now().astimezone()

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def get_jobs(self) -> Dict[str, Dict[str, Any]]:
        """Get jobs."""
        with self._db_session() as session:
            return {
                job.name: {
                    "plugin_id": job.plugin_id,
                    "every": job.every,
                    "reload": job.reload,
                    "async": job.run_async,
                    "history": [
                        {
                            "start_date": job_run.start_date.astimezone().isoformat(),
                            "end_date": job_run.end_date.astimezone().isoformat(),
                            "success": job_run.success,
                        }
                        for job_run in session.execute(
                            select(Jobs_runs.success, Jobs_runs.start_date, Jobs_runs.end_date)
                            .filter_by(job_name=job.name)
                            .order_by(Jobs_runs.end_date.desc())
                            .limit(10)
                        )
                    ],
                    "cache": [
                        {
                            "service_id": cache.service_id,
                            "file_name": cache.file_name,
                            "last_update": cache.last_update.strftime("%Y/%m/%d, %H:%M:%S %Z") if cache.last_update else "Never",
                            "checksum": cache.checksum,
                        }
                        for cache in session.execute(
                            select(Jobs_cache.service_id, Jobs_cache.file_name, Jobs_cache.last_update, Jobs_cache.checksum).filter_by(job_name=job.name)
                        )
                    ],
                }
                for job in session.execute(select(Jobs.name, Jobs.plugin_id, Jobs.every, Jobs.reload, Jobs.run_async)).all()
            }

    def get_job_cache_file(
        self, job_name: str, file_name: str, *, service_id: str = "", plugin_id: str = "", with_info: bool = False, with_data: bool = True
    ) -> Optional[Union[Dict[str, Any], bytes]]:
        """Get job cache file."""
        entities = []
        if with_info:
            entities.extend([Jobs_cache.last_update, Jobs_cache.checksum])
        if with_data:
            entities.append(Jobs_cache.data)

        filters = {"job_name": job_name, "file_name": file_name, "service_id": service_id or None}

        with self._db_session() as session:
            if plugin_id:
                job = session.scalars(select(Jobs).filter_by(name=job_name, plugin_id=plugin_id).limit(1)).first()
                if not job:
                    return None
            data = session.execute(select(*entities).filter_by(**filters).limit(1)).first()

        if not data:
            return None
        elif with_data and not with_info:
            return data.data

        ret_data = {}
        if with_info:
            ret_data["last_update"] = data.last_update.timestamp() if data.last_update is not None else "Never"
            ret_data["checksum"] = data.checksum
        if with_data:
            ret_data["data"] = data.data
        return ret_data

    def get_jobs_cache_files(self, *, with_data: bool = True, job_name: str = "", plugin_id: str = "") -> List[Dict[str, Any]]:
        """Get jobs cache files."""
        with self._db_session() as session:
            filters = {}
            entities = [Jobs_cache.job_name, Jobs_cache.service_id, Jobs_cache.file_name, Jobs_cache.last_update, Jobs_cache.checksum]
            if with_data:
                entities.append(Jobs_cache.data)
            query = select(*entities)

            if job_name:
                query = query.filter_by(job_name=job_name)
                filters["name"] = job_name

            db_cache = session.execute(query).all()

            if not db_cache:
                return []

            if plugin_id:
                filters["plugin_id"] = plugin_id

            query = select(Jobs.name, Jobs.plugin_id)

            if filters:
                query = query.filter_by(**filters)

            jobs = {}
            for job in session.execute(query):
                jobs[job.name] = job.plugin_id

            if not jobs:
                return []

            cache_files = []
            for cache in db_cache:
                if cache.job_name not in jobs:
                    continue
                cache_files.append(
                    {
                        "plugin_id": jobs[cache.job_name],
                        "job_name": cache.job_name,
                        "service_id": cache.service_id,
                        "file_name": cache.file_name,
                        "last_update": cache.last_update if cache.last_update is not None else "Never",
                        "checksum": cache.checksum,
                    }
                )
                if with_data:
                    cache_files[-1]["data"] = cache.data

            return cache_files
