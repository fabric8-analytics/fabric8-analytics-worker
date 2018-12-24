"""go backend for golang.

Revision ID: 097bb617eade
Revises: 3655e38b92bc
Create Date: 2018-10-23 13:42:00.299914

"""

# revision identifiers, used by Alembic.
revision = '097bb617eade'
down_revision = '3655e38b92bc'
branch_labels = None
depends_on = None

from alembic import op


def upgrade():
    """Upgrade the database to a newer revision."""
    connection = op.get_bind()
    connection.execution_options(isolation_level='AUTOCOMMIT')

    connection.execute("""
    ALTER TYPE ecosystem_backend_enum ADD VALUE 'go'
    """)

    connection.execute("""
    UPDATE ecosystems
       SET _backend = 'go'
       WHERE name = 'go'
    """)


def downgrade():
    """Downgrade the database to an older revision."""
    # This script only migrates/fixes data, nothing to downgrade here.
    pass
