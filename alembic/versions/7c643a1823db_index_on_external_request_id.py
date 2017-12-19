"""index on external_request_id.

Revision ID: 7c643a1823db
Revises: f8bb0efac483
Create Date: 2017-11-03 15:07:25.729529

"""

# revision identifiers, used by Alembic.
revision = '7c643a1823db'
down_revision = 'f8bb0efac483'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    """Upgrade the database to a newer revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(op.f('ix_worker_results_external_request_id'), 'worker_results',
                    ['external_request_id'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    """Downgrade the database to an older revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_worker_results_external_request_id'), table_name='worker_results')
    # ### end Alembic commands ###
