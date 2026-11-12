from alembic import context

from app.product import tables
from app.product.db import build_engine, database_url


def migrate(connection):
    context.configure(connection=connection, target_metadata=tables.Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url=database_url(), target_metadata=tables.Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
elif (connection := context.config.attributes.get("connection")) is not None:
    migrate(connection)
else:
    engine = build_engine(database_url())
    try:
        with engine.begin() as connection:
            migrate(connection)
    finally:
        engine.dispose()
