"""Describe change6.241

Revision ID: a101423b1ebe
Revises: 2dd8ff502aaa
Create Date: 2025-06-24 18:05:05.465518

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a101423b1ebe'
down_revision: Union[str, None] = '2dd8ff502aaa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('daily_review_word_links', sa.Column('review_indicator', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('daily_review_word_links', 'review_indicator')
    # ### end Alembic commands ###
