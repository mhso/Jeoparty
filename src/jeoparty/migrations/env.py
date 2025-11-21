import os
import sys
from logging.config import fileConfig

from sqlalchemy import Connection
from alembic import context

from mhooge_flask.database import Base

# Add your project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jeoparty.api.database import Database

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database = Database()

# Set target metadata
target_metadata = Base.metadata


# Define a function to help Alembic correctly identify objects
def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table":
        # Don't drop tables that are in our models
        if name in [t.name for t in target_metadata.sorted_tables] and compare_to is None:
            return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    # Get URL from config or environment
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online(connection: Connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    with database.engine.connect() as conn:
       run_migrations_online(conn)
