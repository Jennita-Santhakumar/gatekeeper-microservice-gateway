"""SQLAlchemy models for posts-service.

NOTE on `user_id`: this column intentionally has NO foreign key constraint
pointing at the users-service's `users` table. Each service in this
microservice architecture owns its own database, and posts-service has no
direct access to the users-service database. Referential integrity of
user_id -> users.id is enforced at the application/gateway layer (or accepted
as eventual/soft consistency), not at the database layer. This is a deliberate
microservice boundary, not an oversight.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Indexed but NOT a foreign key -- see module docstring.
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
