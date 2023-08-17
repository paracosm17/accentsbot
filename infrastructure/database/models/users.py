import datetime
from typing import Optional

from sqlalchemy import BIGINT, Integer, DateTime
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from .base import Base, TimestampMixin


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BIGINT, index=True, unique=True)
    username: Mapped[Optional[str]] = mapped_column(String(128))
    first_name: Mapped[str] = mapped_column(String(128))
    words = mapped_column(Integer, nullable=False, default=0)
    added_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __repr__(self):
        return f"<User {self.telegram_id} {self.username} {self.first_name}>"
