from __future__ import annotations

from alembic import op

from memory_engine.db.base import Base
from memory_engine.db import models  # noqa: F401

revision = "20260409_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE SCHEMA IF NOT EXISTS control")
    op.execute("CREATE SCHEMA IF NOT EXISTS runtime")
    op.execute("CREATE SCHEMA IF NOT EXISTS ops")
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
    op.execute("DROP SCHEMA IF EXISTS ops CASCADE")
    op.execute("DROP SCHEMA IF EXISTS runtime CASCADE")
    op.execute("DROP SCHEMA IF EXISTS control CASCADE")
