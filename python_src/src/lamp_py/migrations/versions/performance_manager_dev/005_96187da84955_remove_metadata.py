"""remove_metadata

Revision ID: 96187da84955
Revises: 45dedc21086e
Create Date: 2023-12-28 12:18:25.412282

check that all information in the metadata table has been copied to the
metadata database before dropping the table and its indexes entirely.
"""

import time

from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.sql import text
import logging
import sqlalchemy as sa

from lamp_py.postgres.postgres_utils import DatabaseIndex, DatabaseManager
from lamp_py.postgres.metadata_schema import MetadataLog

# revision identifiers, used by Alembic.
revision = "96187da84955"
down_revision = "45dedc21086e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    while True:
        try:
            rpm_db_manager = DatabaseManager(
                db_index=DatabaseIndex.RAIL_PERFORMANCE_MANAGER
            )
            md_db_manager = DatabaseManager(db_index=DatabaseIndex.METADATA)

            with rpm_db_manager.session.begin() as session:
                legacy_result = session.execute(
                    text("SELECT path FROM metadata_log")
                )
                legacy_paths = set(
                    [record[0] for record in legacy_result.fetchall()]
                )

            modern_result = md_db_manager.select_as_list(
                sa.select(MetadataLog.path)
            )
            modern_paths = set([record["path"] for record in modern_result])

            missing_paths = legacy_paths - modern_paths
            if len(missing_paths) == 0:
                break
            else:
                logging.error(
                    "Detected %s paths in Legacy Metadata Table not found in Metadata Database",
                    len(missing_paths),
                )
        except ProgrammingError as error:
            # Error 42P01 is an 'Undefined Table' error. This occurs when there is
            # no metadata_log table in the rail performance manager database
            #
            # Raise all other sql errors
            original_error = error.orig
            if (
                original_error is not None
                and hasattr(original_error, "pgcode")
                and original_error.pgcode == "42P01"
            ):
                logging.info("No Metadata Table in Rail Performance Manager")
                legacy_paths = set()
            else:
                logging.exception(
                    "Programming Error when checking Metadata Log"
                )
                time.sleep(15)
                continue

        except Exception as error:
            logging.exception("Programming Error when checking Metadata Log")
            time.sleep(15)
            continue

    op.drop_index("ix_metadata_log_not_processed", table_name="metadata_log")
    op.drop_table("metadata_log")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "metadata_log",
        sa.Column("pk_id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column(
            "processed", sa.BOOLEAN(), autoincrement=False, nullable=True
        ),
        sa.Column(
            "process_fail", sa.BOOLEAN(), autoincrement=False, nullable=True
        ),
        sa.Column(
            "path", sa.VARCHAR(length=256), autoincrement=False, nullable=False
        ),
        sa.Column(
            "created_on",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("pk_id", name="metadata_log_pkey"),
        sa.UniqueConstraint("path", name="metadata_log_path_key"),
    )
    op.create_index(
        "ix_metadata_log_not_processed",
        "metadata_log",
        ["path"],
        unique=False,
        postgresql_where="(processed = false)",
    )
    # ### end Alembic commands ###
