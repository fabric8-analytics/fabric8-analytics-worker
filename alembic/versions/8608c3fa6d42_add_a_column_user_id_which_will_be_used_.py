"""Add a column user_id which will be used to persist uuid.

Revision ID: 8608c3fa6d42
Revises: 62010067944d
Create Date: 2020-12-28 18:42:36.142944

"""

# revision identifiers, used by Alembic.
revision = '8608c3fa6d42'
down_revision = '62010067944d'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade():
    """Upgrade the database to a newer revision."""
    op.add_column('stack_analyses_request', sa.Column('user_id',
                  postgresql.UUID(as_uuid=True), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    """Downgrade the database to an older revision."""
    op.drop_column('stack_analyses_request', 'user_id')
# ### end Alembic commands ###
