"""Add recommendation_feedback table into the database.

Revision ID: da53445aabad
Revises: cd05b43f27e5
Create Date: 2018-01-17 12:47:40.573316

"""

# revision identifiers, used by Alembic.
revision = 'da53445aabad'
down_revision = 'cd05b43f27e5'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    """Upgrade the database to a newer revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('recommendation_feedback',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('package_name', sa.String(
                        length=255), nullable=False),
                    sa.Column('recommendation_type', sa.String(
                        length=255), nullable=False),
                    sa.Column('feedback_type', sa.Boolean(), nullable=False),
                    sa.Column('ecosystem_id', sa.Integer(), nullable=True),
                    sa.Column('stack_id', sa.String(length=64), nullable=True),
                    sa.ForeignKeyConstraint(
                        ['ecosystem_id'], ['ecosystems.id'], ),
                    sa.ForeignKeyConstraint(
                        ['stack_id'], ['stack_analyses_request.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    # ### end Alembic commands ###


def downgrade():
    """Downgrade the database to an older revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('recommendation_feedback')
    # ### end Alembic commands ###
