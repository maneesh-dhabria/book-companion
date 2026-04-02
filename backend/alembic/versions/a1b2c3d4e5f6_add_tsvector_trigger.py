"""add tsvector trigger for search_index

Revision ID: a1b2c3d4e5f6
Revises: 8b38146465ab
Create Date: 2026-04-02 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "8b38146465ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the trigger function to auto-populate tsvector on insert/update
    op.execute("""
        CREATE OR REPLACE FUNCTION search_index_tsvector_update() RETURNS trigger AS $$
        BEGIN
          NEW.tsvector := to_tsvector('english', NEW.chunk_text);
          RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)

    # Create the trigger on the search_index table
    op.execute("""
        CREATE TRIGGER tsvector_update
        BEFORE INSERT OR UPDATE ON search_index
        FOR EACH ROW EXECUTE FUNCTION search_index_tsvector_update();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS tsvector_update ON search_index;")
    op.execute("DROP FUNCTION IF EXISTS search_index_tsvector_update();")
