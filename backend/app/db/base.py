"""SQLAlchemy declarative base. Importing `models` registers all tables on `Base.metadata`,
which Alembic's env.py uses as the autogenerate target for future migrations."""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Re-export models so `import app.db.base` populates metadata.
from app.db import models  # noqa: E402,F401
