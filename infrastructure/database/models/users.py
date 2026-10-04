from datetime import datetime

from sqlalchemy import BIGINT, TIMESTAMP, Boolean, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedMixin


class User(Base, CreatedMixin):
    __tablename__ = "user"

    user_id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=False, unique=True)
    username: Mapped[str | None] = mapped_column(String(128))
    full_name: Mapped[str] = mapped_column(String(128))
    language_code: Mapped[str | None] = mapped_column(String(4), nullable=True)

    banned: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_active: Mapped[datetime | None] = mapped_column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )
    words: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return (
            f"User({self.user_id=} {self.username=} {self.full_name=} "
            f"{self.banned=} {self.active=} {self.last_active=} {self.words=})"
        )
