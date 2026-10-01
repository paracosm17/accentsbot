from datetime import datetime, date, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert

from infrastructure.database.models import User
from infrastructure.database.repo.base import BaseRepo


class UserRepo(BaseRepo):
    async def update_or_create_user(
            self,
            user_id: int,
            full_name: str,
            language_code: str,
            username: Optional[str] = None,
    ):
        insert_user_statement = select(User).from_statement(
            insert(User)
            .values(
                user_id=user_id,
                username=username,
                full_name=full_name,
                language_code=language_code,
                active=True,
                last_active=datetime.now()
            )
            .returning(User)
            .on_conflict_do_update(
                index_elements=[User.user_id],
                set_=dict(
                    username=username,
                    full_name=full_name,
                    language_code=language_code,
                    active=True,
                    last_active=datetime.now()
                ),
            )
        )
        result = await self.session.execute(insert_user_statement)

        await self.session.commit()
        return result.scalar_one()

    async def ban_user(self, user_id: int):
        user = await self.session.execute(select(User).where(User.user_id == user_id))
        user_scalar: User = user.scalar()
        if user_scalar is None:
            return False
        user_scalar.banned = True
        await self.session.commit()
        return True

    async def unban_user(self, user_id: int):
        user = await self.session.execute(select(User).where(User.user_id == user_id))
        user_scalar: User = user.scalar()
        if user_scalar is None:
            return False
        user_scalar.banned = False
        await self.session.commit()
        return True

    async def active_user(self, user_id: int, active: bool) -> bool:
        user = await self.session.execute(select(User).where(User.user_id == user_id))
        user_scalar: User = user.scalar()
        if user_scalar is None:
            return False
        user_scalar.active = active
        await self.session.commit()
        return True

    async def do_user_exists(self, user_id: int) -> bool:
        user = await self.session.execute(select(User).where(User.user_id == user_id))
        user_scalar: User = user.scalar()
        if user_scalar is None:
            return False
        return True

    async def users_count(self, only_active: bool = False) -> int:
        if not only_active:
            users = await self.session.execute(select(func.count()).select_from(User))
        else:
            users = await self.session.execute(select(func.count()).select_from(User).where(User.active==True))
        return users.scalar()

    async def get_all_users_ids(self):
        users = await self.session.execute(select(User.user_id))
        return users.scalars().all()

    async def get_active_users(self, count: int, random: bool = True, after_ege: bool = True):
        if random:
            if after_ege:
                users = await self.session.execute(
                    select(User.user_id).where(User.active == True).filter(
                        func.date(User.created_at) > date(year=2023, month=6, day=1)
                    ).order_by(func.random()).limit(count)
                )
            else:
                users = await self.session.execute(
                    select(User.user_id).where(User.active == True).order_by(func.random()).limit(count)
                )
        else:
            if after_ege:
                users = await self.session.execute(
                    select(User.user_id).where(User.active == True).filter(
                        func.date(User.created_at) > date(year=2023, month=6, day=1)
                    ).order_by(User.created_at.desc()).limit(count)
                )
            else:
                users = await self.session.execute(
                    select(User.user_id).where(User.active == True).order_by(User.created_at.desc()).limit(count)
                )
        return users.scalars().all()

    async def add_word(self, user_id: int):
        user = await self.session.execute(select(User).where(User.user_id == user_id))
        user = user.scalar()
        user.words += 1
        await self.session.commit()
        return user.words

    async def get_words_count_by_id(self, user_id: int) -> int:
        user = await self.session.execute(select(User).where(User.user_id == user_id))
        user = user.scalar()
        return user.words

    async def get_biggest_words(self):
        result = await self.session.execute(select(User).order_by(User.words.desc()).limit(20))
        return result.scalars().all()

    async def get_users_created_count_by_days(self, days: int) -> int:
        users = await self.session.execute(
            select(func.count()).select_from(User).filter(
                func.date(User.created_at) > date.today() - timedelta(days=days)
            )
        )
        return users.scalar()

    async def get_users_active_count_by_days(self, days: int) -> int:
        users = await self.session.execute(
            select(func.count()).select_from(User).filter(
                func.date(User.last_active) > date.today() - timedelta(days=days)
            )
        )
        return users.scalar()
