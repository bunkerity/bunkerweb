from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "src/common/db/alembic/sqlite_versions/a41d5e9b7c20_normalize_metrics_redis_ttl.py"


class MetricsTtlMigrationTest(unittest.TestCase):
    def test_count_shorthand_is_normalized(self):
        spec = spec_from_file_location("normalize_metrics_redis_ttl", MIGRATION)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)

        engine = sa.create_engine("sqlite://")
        with engine.begin() as connection:
            for table, column in (("bw_global_values", "value"), ("bw_services_settings", "value"), ("bw_template_settings", "default")):
                connection.execute(sa.text(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY, setting_id TEXT, "{column}" TEXT)'))
                connection.execute(
                    sa.text(f'INSERT INTO {table} (id, setting_id, "{column}") VALUES (:id, :setting_id, :value)'),
                    [{"id": index, "setting_id": "METRICS_REDIS_TTL", "value": value} for index, value in enumerate(("2m", "500k", "86400", "0"), 1)],
                )

            module.op = Operations(MigrationContext.configure(connection))
            module.upgrade()

            for table, column in (("bw_global_values", "value"), ("bw_services_settings", "value"), ("bw_template_settings", "default")):
                values = connection.execute(sa.text(f'SELECT "{column}" FROM {table} ORDER BY id')).scalars().all()
                self.assertEqual(values, ["2000000", "500000", "86400", "0"])


if __name__ == "__main__":
    unittest.main()
