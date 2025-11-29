"""recreate_all

Revision ID: 9e063632a2ba
Revises: 9f34d3373d63
Create Date: 2025-11-27 19:04:28.963790

"""
from typing import Sequence, Union
import sys, os

from alembic import op
import sqlalchemy as sa

# Add your project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))



# revision identifiers, used by Alembic.
revision: str = '9e063632a2ba'
down_revision: Union[str, None] = '9f34d3373d63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    tables = 


def downgrade() -> None:
    """Downgrade schema."""
    pass