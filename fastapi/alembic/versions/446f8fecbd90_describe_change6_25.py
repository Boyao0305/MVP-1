"""Describe change6.25

Revision ID: 446f8fecbd90
Revises: 865504454a25
Create Date: 2025-06-26 05:21:42.174692

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '446f8fecbd90'
down_revision: Union[str, None] = '865504454a25'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('learning_logs', 'outline',
               existing_type=mysql.VARCHAR(length=1024),
               type_=sa.String(length=4096),
               existing_nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('learning_logs', 'outline',
               existing_type=sa.String(length=4096),
               type_=mysql.VARCHAR(length=1024),
               existing_nullable=True)
    # ### end Alembic commands ###
