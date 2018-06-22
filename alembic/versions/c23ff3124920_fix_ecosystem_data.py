"""fix ecosystem data.

Revision ID: c23ff3124920
Revises: 43360d9467b9
Create Date: 2018-06-21 19:49:32.491944

"""

# revision identifiers, used by Alembic.
revision = 'c23ff3124920'
down_revision = '43360d9467b9'
branch_labels = None
depends_on = None

from alembic import op


def upgrade():
    """Upgrade the database to a newer revision."""
    connection = op.get_bind()

    connection.execute("""
    UPDATE ecosystems
       SET fetch_url = 'https://repo.maven.apache.org/maven2/'
     WHERE name = 'maven'
    """)

    connection.execute("""
    UPDATE ecosystems
       SET fetch_url = 'https://pypi.org/pypi//'
     WHERE name = 'pypi'
    """)


def downgrade():
    """Downgrade the database to an older revision."""
    # This script only migrates/fixes data, nothing to downgrade here.
    pass
