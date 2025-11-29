import traceback
from typing import List
from sqlalchemy import Table, select, column
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoSuchTableError

from jeoparty.api.database import Database
from jeoparty.api.orm.models import Base

ARRAY_SIZE = 1000

def copy_to_table(source_table: Table, dest_table: Table, session: Session, columns: List[str] | None = None):
    total = 0

    select_vals = [source_table] if columns is None else [source_table.columns[col] for col in columns]

    select_query = select(*select_vals)
    insert_sql = dest_table.insert()

    results = session.execute(select_query)
    while True:
        recs = results.fetchmany(ARRAY_SIZE)
        _total = len(recs)
        total += _total

        if _total > 0:
            params = [row._asdict() for row in recs]
            session.execute(insert_sql, params)
            session.commit()

        if _total < ARRAY_SIZE:
            break

    print(f'{total} records copied from {source_table.name} to {dest_table.name}')

def clone_table(source_table: Table, to_table: str, session: Session, engine):
    try:
        dest_table = source_table.to_metadata(source_table.metadata, name=to_table)
        dest_table.create(engine)

        copy_to_table(source_table, dest_table, session)

        return dest_table
    except NoSuchTableError:
        print(f"Table '{source_table.name}' not found")
        traceback.print_exc()
        return None

filters = {}

database = Database()
with database as session:
    database.engine.update_execution_options(arraysize=ARRAY_SIZE)

    tables = [Base.metadata.tables[name] for name in Base.metadata.tables]

    for old_table in tables:
        # Create backup table
        new_table = clone_table(old_table, f"{old_table.name}_backup", session, database.engine)
        if new_table is None:
            continue

        # Drop and recreate original table
        old_table.drop(database.engine)
        old_table.create(database.engine)

        copy_to_table(new_table, old_table, session, filters.get(old_table.name))
        new_table.drop(database.engine)
