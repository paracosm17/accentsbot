from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from infrastructure.database.models import User
from infrastructure.database.repo.base import BaseRepo


class UserRepo(BaseRepo):
    async def update_or_create_user(
        self,
        user_id: int,
        full_name: str,
        language_code: str | None,
        username: str | None = None,
    ) -> User:
        now = datetime.now()
        statement = select(User).from_statement(
            insert(User)
            .values(
                user_id=user_id,
                username=username,
                full_name=full_name,
                language_code=language_code,
                active=True,
                last_active=now,
            )
            .returning(User)
            .on_conflict_do_update(
                index_elements=[User.user_id],
                set_={
                    "username": username,
                    "full_name": full_name,
                    "language_code": language_code,
                    "active": True,
                    "last_active": now,
                },
            )
        )
        result = await self.session.execute(statement)
        await self.session.commit()
        return result.scalar_one()

    async def ban_user(self, user_id: int) -> bool:
        user = await self.session.scalar(select(User).where(User.user_id == user_id))
        if user is None:
            return False
        user.banned = True
        await self.session.commit()
        return True

    async def unban_user(self, user_id: int) -> bool:
        user = await self.session.scalar(select(User).where(User.user_id == user_id))
        if user is None:
            return False
        user.banned = False
        await self.session.commit()
        return True

    async def active_user(self, user_id: int, active: bool) -> bool:
        user = await self.session.scalar(select(User).where(User.user_id == user_id))
        if user is None:
            return False
        user.active = active
        await self.session.commit()
        return True

    async def do_user_exists(self, user_id: int) -> bool:
        return (
            await self.session.scalar(select(User.user_id).where(User.user_id == user_id))
            is not None
        )

    async def users_count(self, only_active: bool = False) -> int:
        statement = select(func.count()).select_from(User)
        if only_active:
            statement = statement.where(User.active.is_(True))
        return int((await self.session.execute(statement)).scalar_one())

    async def get_all_users_ids(self) -> list[int]:
        users = await self.session.execute(select(User.user_id))
        return list(users.scalars().all())

    async def get_active_users(
        self,
        count: int,
        random: bool = True,
        after_ege: bool = True,
    ) -> list[int]:
        if count <= 0:
            return []

        statement = select(User.user_id).where(User.active.is_(True))
        if after_ege:
            # Preserve the legacy SQL semantics: DATE(created_at) > 2023-06-01.
            statement = statement.where(User.created_at >= datetime(2023, 6, 2))
        statement = statement.order_by(func.random() if random else User.created_at.desc()).limit(
            count
        )
        users = await self.session.execute(statement)
        return list(users.scalars().all())

    async def add_word(self, user_id: int) -> int:
        statement = (
            update(User)
            .where(User.user_id == user_id)
            .values(words=User.words + 1)
            .returning(User.words)
        )
        words = (await self.session.execute(statement)).scalar_one_or_none()
        if words is None:
            raise LookupError(f"user {user_id} is missing")
        await self.session.commit()
        return int(words)

    async def get_words_count_by_id(self, user_id: int) -> int:
        words = await self.session.scalar(select(User.words).where(User.user_id == user_id))
        if words is None:
            raise LookupError(f"user {user_id} is missing")
        return int(words)

    async def get_biggest_words(self) -> list[User]:
        result = await self.session.execute(select(User).order_by(User.words.desc()).limit(20))
        return list(result.scalars().all())

    @staticmethod
    def _calendar_window_start(days: int) -> datetime:
        if days <= 0:
            raise ValueError("days must be positive")
        # Preserve the legacy DATE(column) > CURRENT_DATE - days behaviour while
        # keeping the timestamp column usable by PostgreSQL indexes.
        first_date = date.today() - timedelta(days=days - 1)
        return datetime.combine(first_date, time.min)

    async def get_users_created_count_by_days(self, days: int) -> int:
        threshold = self._calendar_window_start(days)
        statement = select(func.count()).select_from(User).where(User.created_at >= threshold)
        return int((await self.session.execute(statement)).scalar_one())

    async def get_users_active_count_by_days(self, days: int) -> int:
        threshold = self._calendar_window_start(days)
        statement = select(func.count()).select_from(User).where(User.last_active >= threshold)
        return int((await self.session.execute(statement)).scalar_one())
