"""Upgrade to version 1.7.0~beta

Revision ID: e8b4d91f6a20
Revises: b4e0d05e52e7
Create Date: 2026-07-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e8b4d91f6a20"
down_revision: Union[str, None] = "b4e0d05e52e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    op.execute("UPDATE bw_metadata SET version = '1.7.0~beta' WHERE id = 1")
    op.execute("UPDATE bw_metadata SET last_pro_check = NULL WHERE id = 1")
    for value in ("web_cache", "resource_groups", "certificates"):
        op.execute(f"ALTER TYPE api_resource_enum ADD VALUE IF NOT EXISTS '{value}'")

    resource_kinds = postgresql.ENUM("ip", "country", "asn", "rdns", "user_agent", "uri", name="resource_kinds_enum")
    resource_types = postgresql.ENUM("certificate", name="resource_types_enum")
    certificate_sources = postgresql.ENUM("letsencrypt", "customcert", "selfsigned", name="certificate_sources_enum")
    resource_kinds.create(bind, checkfirst=True)
    resource_types.create(bind, checkfirst=True)
    certificate_sources.create(bind, checkfirst=True)

    if "bw_resource_groups" not in tables:
        op.create_table(
            "bw_resource_groups",
            sa.Column("id", sa.String(length=256), nullable=False),
            sa.Column("name", sa.String(length=256), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "method",
                postgresql.ENUM("api", "ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum", create_type=False),
                nullable=False,
            ),
            sa.Column("plugin_id", sa.String(length=64), nullable=True),
            sa.Column("creation_date", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_update", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["plugin_id"], ["bw_plugins.id"], onupdate="cascade", ondelete="cascade"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )
        op.create_index("ix_bw_resource_groups_plugin_id", "bw_resource_groups", ["plugin_id"])
    if "bw_resource_group_entries" not in tables:
        op.create_table(
            "bw_resource_group_entries",
            sa.Column("id", sa.Integer(), sa.Identity(start=1, increment=1), nullable=False),
            sa.Column("group_id", sa.String(length=256), nullable=False),
            sa.Column("kind", postgresql.ENUM(*resource_kinds.enums, name="resource_kinds_enum", create_type=False), nullable=False),
            sa.Column("value", sa.Text(), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("order", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["group_id"], ["bw_resource_groups.id"], onupdate="cascade", ondelete="cascade"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("group_id", "order"),
        )
        op.create_index("ix_bw_resource_group_entries_group_id", "bw_resource_group_entries", ["group_id"])
    if "bw_resources" not in tables:
        op.create_table(
            "bw_resources",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("type", postgresql.ENUM("certificate", name="resource_types_enum", create_type=False), nullable=False),
            sa.Column("name", sa.String(length=256), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("creation_date", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_update", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("type", "name"),
        )
    if "bw_certificates" not in tables:
        op.create_table(
            "bw_certificates",
            sa.Column("resource_id", sa.String(length=36), nullable=False),
            sa.Column(
                "source",
                postgresql.ENUM("letsencrypt", "customcert", "selfsigned", name="certificate_sources_enum", create_type=False),
                nullable=False,
            ),
            sa.Column("certificate_pem", sa.Text(), nullable=False),
            sa.Column("private_key_ciphertext", sa.LargeBinary(length=(2**32) - 1), nullable=False),
            sa.Column("private_key_nonce", sa.LargeBinary(length=12), nullable=False),
            sa.Column("private_key_key_id", sa.String(length=128), nullable=False),
            sa.Column("common_name", sa.String(length=256), nullable=False),
            sa.Column("sans", sa.Text(), nullable=False),
            sa.Column("issuer", sa.String(length=512), nullable=False),
            sa.Column("serial_number", sa.String(length=128), nullable=False),
            sa.Column("fingerprint", sa.String(length=64), nullable=False),
            sa.Column("key_type", sa.String(length=64), nullable=False),
            sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
            sa.Column("valid_to", sa.DateTime(timezone=True), nullable=False),
            sa.Column("renewal_metadata", sa.Text(), nullable=False),
            sa.Column("last_renewal", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_renewal", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("revoked", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["resource_id"], ["bw_resources.id"], onupdate="cascade", ondelete="cascade"),
            sa.PrimaryKeyConstraint("resource_id"),
            sa.UniqueConstraint("fingerprint"),
        )
        op.create_index("ix_bw_certificates_common_name", "bw_certificates", ["common_name"])
        op.create_index("ix_bw_certificates_valid_to", "bw_certificates", ["valid_to"])
    if "bw_resource_attachments" not in tables:
        op.create_table(
            "bw_resource_attachments",
            sa.Column("id", sa.Integer(), sa.Identity(start=1, increment=1), nullable=False),
            sa.Column("resource_id", sa.String(length=36), nullable=False),
            sa.Column("service_id", sa.String(length=256), nullable=False),
            sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("creation_date", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["resource_id"], ["bw_resources.id"], onupdate="cascade", ondelete="cascade"),
            sa.ForeignKeyConstraint(["service_id"], ["bw_services.id"], onupdate="cascade", ondelete="cascade"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("resource_id", "service_id"),
        )
        op.create_index("ix_bw_resource_attachments_resource_id", "bw_resource_attachments", ["resource_id"])
        op.create_index("ix_bw_resource_attachments_service_primary", "bw_resource_attachments", ["service_id", "is_primary"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    for table in ("bw_resource_attachments", "bw_certificates", "bw_resources", "bw_resource_group_entries", "bw_resource_groups"):
        if table in tables:
            op.drop_table(table)
    postgresql.ENUM("letsencrypt", "customcert", "selfsigned", name="certificate_sources_enum").drop(bind, checkfirst=True)
    postgresql.ENUM("certificate", name="resource_types_enum").drop(bind, checkfirst=True)
    postgresql.ENUM("ip", "country", "asn", "rdns", "user_agent", "uri", name="resource_kinds_enum").drop(bind, checkfirst=True)
    op.execute("DELETE FROM bw_api_user_permissions WHERE resource_type IN ('web_cache', 'resource_groups', 'certificates')")
    # PostgreSQL cannot safely remove enum labels in place; retaining them is harmless.
    op.execute("UPDATE bw_metadata SET version = '1.6.12' WHERE id = 1")
