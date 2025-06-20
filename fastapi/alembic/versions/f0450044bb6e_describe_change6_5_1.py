"""Describe change6.5.1

Revision ID: f0450044bb6e
Revises: f95f1c9e8efb
Create Date: 2025-06-05 15:12:44.197576

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'f0450044bb6e'
down_revision: Union[str, None] = 'f95f1c9e8efb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('learning_settings', 'average_caiji',
               existing_type=mysql.FLOAT(),
               type_=sa.Integer(),
               existing_nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('learning_settings', 'average_caiji',
               existing_type=sa.Integer(),
               type_=mysql.FLOAT(),
               existing_nullable=True)
    # ### end Alembic commands ###
