import datetime
from typing import Optional
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.functions import func

from infrastructure.database.models import User
from infrastructure.database.repo.base import BaseRepo


class UserRepo(BaseRepo):
    async def get_or_create_user(
        self,
        telegram_id: int,
        first_name: str,
        username: Optional[str] = None,
    ):

        insert_stmt = select(User).from_statement(
            insert(User)
            .values(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                added_at=datetime.datetime.utcnow()
            )
            .returning(User)
            .on_conflict_do_update(
                index_elements=[User.telegram_id],
                set_=dict(
                    username=username,
                    first_name=first_name,
                ),
            )
        )
        result = await self.session.scalars(insert_stmt)

        await self.session.commit()
        return result.first()

    async def add_word(self, user_id: int):
        user = await self.session.execute(select(User).where(User.telegram_id == user_id))
        user = user.scalar()
        user.words += 1
        await self.session.commit()
        return user.words

    async def get_words_count_by_id(self, user_id: int) -> int:
        user = await self.session.execute(select(User).where(User.telegram_id == user_id))
        user = user.scalar()
        return user.words

    async def users_count(self) -> int:
        length = await self.session.execute(select(User))
        return len(length.scalars().all())

    async def get_biggest_words(self):
        result = await self.session.execute(select(User).order_by(User.words.desc()).limit(20))
        return result.scalars().all()

    async def get_users_today(self) -> int:
        result = await self.session.execute(select(User).filter(func.date(User.added_at) == date.today()))
        return len(result.scalars().all())
