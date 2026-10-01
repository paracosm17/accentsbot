from datetime import datetime
from typing import Optional

from sqlalchemy import BIGINT, Boolean, Integer
from sqlalchemy import String, func, TIMESTAMP
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from .base import Base, CreatedMixin


class User(Base, CreatedMixin):
    user_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=False, unique=True)
    username: Mapped[Optional[str]] = mapped_column(String(128))
    full_name: Mapped[str] = mapped_column(String(128))
    language_code: Mapped[str] = mapped_column(String(4), nullable=True)  # !!! nullable

    banned: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_active: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now(),
                                                  onupdate=func.now(), nullable=True)  # !!! nullable

    words: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self):
        return (f"User({self.user_id=} {self.username=} {self.full_name=} "
                f"{self.banned=} {self.active=} {self.last_active=} {self.words=})")

    __tablename__ = "user"
