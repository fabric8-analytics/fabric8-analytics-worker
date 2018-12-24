"""add redhat-maven ecosystem.

Revision ID: c3ea37a6ebc5
Revises: c23ff3124920
Create Date: 2018-06-21 20:08:09.990207

"""

# revision identifiers, used by Alembic.
revision = 'c3ea37a6ebc5'
down_revision = 'c23ff3124920'
branch_labels = None
depends_on = None

from alembic import op
from f8a_worker.models import Ecosystem


def upgrade():
    """Upgrade the database to a newer revision."""
    op.bulk_insert(Ecosystem.__table__, [
        {
            'id': 7,
            'name': 'redhat-maven',
            '_backend': 'maven',
            'url': 'https://maven.repository.redhat.com/ga/',
            'fetch_url': 'https://maven.repository.redhat.com/ga/'}
    ])


def downgrade():
    """Downgrade the database to an older revision."""
    # We want to keep the data there. Thus do nothing here.
    pass
