"""Describe change6.15

Revision ID: ce31f27f8eca
Revises: 52276f91730c
Create Date: 2025-06-15 13:44:35.585033

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'ce31f27f8eca'
down_revision: Union[str, None] = '52276f91730c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('users', 'phone_number',
               existing_type=mysql.INTEGER(),
               type_=sa.String(length=255),
               nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('users', 'phone_number',
               existing_type=sa.String(length=255),
               type_=mysql.INTEGER(),
               nullable=True)
    # ### end Alembic commands ###
