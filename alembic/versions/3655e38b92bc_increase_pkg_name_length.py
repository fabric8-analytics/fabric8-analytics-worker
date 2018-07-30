"""increase pkg name length.

Revision ID: 3655e38b92bc
Revises: 35180d0f1ced
Create Date: 2018-07-30 05:06:10.321980

"""

# revision identifiers, used by Alembic.
revision = '3655e38b92bc'
down_revision = '35180d0f1ced'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    """Upgrade the database to a newer revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        'packages', 'name',
        existing_type=sa.VARCHAR(length=255),
        type_=sa.String(length=2048),
        existing_nullable=True
    )
    # ### end Alembic commands ###


def downgrade():
    """Downgrade the database to an older revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        'packages', 'name',
        existing_type=sa.String(length=2048),
        type_=sa.VARCHAR(length=255),
        existing_nullable=True
    )
    # ### end Alembic commands ###
