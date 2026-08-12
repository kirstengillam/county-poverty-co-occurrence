from sqlalchemy import Engine, create_engine

from cpco.config import DATABASE_URL


def get_engine() -> Engine:
    return create_engine(DATABASE_URL)
