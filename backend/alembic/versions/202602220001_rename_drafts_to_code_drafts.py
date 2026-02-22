"""rename drafts table to code_drafts

Revision ID: 202602220001
Revises: 202602210001
Create Date: 2026-02-22 15:20:01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202602220001"
down_revision: Union[str, None] = "202602210001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    has_drafts = _table_exists(bind, "drafts")
    has_code_drafts = _table_exists(bind, "code_drafts")

    # Legacy migration created "drafts" but ORM expects "code_drafts".
    if has_drafts and not has_code_drafts:
        op.rename_table("drafts", "code_drafts")


def downgrade() -> None:
    bind = op.get_bind()
    has_drafts = _table_exists(bind, "drafts")
    has_code_drafts = _table_exists(bind, "code_drafts")

    if has_code_drafts and not has_drafts:
        op.rename_table("code_drafts", "drafts")
