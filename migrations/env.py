from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

from lib.db import Base  # noqa: F401  (imports every model onto the metadata)
from lib.db.session import database

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    """URL from ``-x url=...``, else ``DATABASE_URL`` from the environment."""
    override = context.get_x_argument(as_dictionary=True).get("url")
    if override:
        return override
    if not database.configured:
        raise RuntimeError(
            "DATABASE_URL is not set - export it or run "
            "'alembic -x url=postgresql+psycopg://... upgrade head'"
        )
    return database.url.render_as_string(hide_password=False)


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine

    connectable = create_engine(_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
