"""Legacy SQLAlchemy model definitions.

Runtime request handling in this repository uses the sqlite3 repository layer
implemented in `weave.core` and `weave.db`.

This module is retained only for historical Alembic compatibility.
"""

# pyright: reportMissingImports=false

try:
    from sqlalchemy import (
        Boolean,
        Column,
        DateTime,
        ForeignKey,
        Integer,
        String,
        Text,
    )
    from sqlalchemy.orm import declarative_base

    Base = declarative_base()

    class User(Base):
        __tablename__ = "users"

        id = Column(Integer, primary_key=True)
        name = Column(String(120), nullable=False)
        username = Column(String(80), nullable=False, unique=True)
        email = Column(String(255), nullable=False, unique=True)
        phone = Column(String(50), nullable=False)
        password_hash = Column(Text, nullable=False)
        role = Column(String(30), nullable=False, default="member")
        status = Column(String(30), nullable=False, default="pending")
        join_date = Column(String(40), nullable=False)

    class Event(Base):
        __tablename__ = "events"

        id = Column(Integer, primary_key=True)
        title = Column(String(200), nullable=False)
        description = Column(Text, nullable=False, default="")
        location = Column(String(200), nullable=False, default="")
        event_date = Column(String(40), nullable=False)
        max_participants = Column(Integer, nullable=False, default=0)
        created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
        created_at = Column(String(40), nullable=False)
        updated_at = Column(String(40), nullable=True)

    class Participant(Base):
        __tablename__ = "participants"

        id = Column(Integer, primary_key=True)
        event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
        user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
        status = Column(String(30), nullable=False, default="registered")
        created_at = Column(String(40), nullable=False)
        updated_at = Column(String(40), nullable=False)

    class Post(Base):
        __tablename__ = "posts"

        id = Column(Integer, primary_key=True)
        category = Column(String(20), nullable=False)
        title = Column(String(255), nullable=False)
        content = Column(Text, nullable=False, default="")
        is_pinned = Column(Boolean, nullable=False, default=False)
        publish_at = Column(String(40), nullable=True)
        author_id = Column(Integer, ForeignKey("users.id"), nullable=True)
        created_at = Column(String(40), nullable=False)
        updated_at = Column(String(40), nullable=False)

    class AuditLog(Base):
        __tablename__ = "audit_logs"

        id = Column(Integer, primary_key=True)
        actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
        action = Column(String(100), nullable=False)
        target_type = Column(String(50), nullable=False, default="")
        target_id = Column(Integer, nullable=True)
        ip = Column(String(100), nullable=False, default="")
        user_agent = Column(String(500), nullable=False, default="")
        created_at = Column(String(40), nullable=False)

except ModuleNotFoundError:

    class _BaseFallback:
        metadata = None

    Base = _BaseFallback()
