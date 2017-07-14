"""update api_requests table

Revision ID: 46a6ec96f351
Revises: f5c853b83d41
Create Date: 2017-07-05 16:29:18.831433

"""

# revision identifiers, used by Alembic.
revision = '46a6ec96f351'
down_revision = 'f5c853b83d41'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('api_requests', sa.Column('api_name', sa.String(length=256), nullable=False))
    op.alter_column('api_requests', 'recommendation',
               existing_type=postgresql.JSON(astext_type=sa.Text()),
               nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('api_requests', 'recommendation',
               existing_type=postgresql.JSON(astext_type=sa.Text()),
               nullable=False)
    op.drop_column('api_requests', 'api_name')
    # ### end Alembic commands ###
