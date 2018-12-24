"""fix pypi url.

Revision ID: 35180d0f1ced
Revises: c3ea37a6ebc5
Create Date: 2018-06-28 11:51:17.555039

"""

# revision identifiers, used by Alembic.
revision = '35180d0f1ced'
down_revision = 'c3ea37a6ebc5'
branch_labels = None
depends_on = None

from alembic import op


def upgrade():
    """Upgrade the database to a newer revision."""
    connection = op.get_bind()

    connection.execute("""
    UPDATE ecosystems
       SET fetch_url = 'https://pypi.org/pypi/'
     WHERE name = 'pypi'
    """)


def downgrade():
    """Downgrade the database to an older revision."""
    # This script only migrates/fixes data, nothing to downgrade here.
    pass
