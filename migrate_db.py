import asyncio
import asyncpg
import sqlite3
import datetime
import os


async def migrate_data():
    # Подключение к базе данных SQLite3
    sqlite_conn = sqlite3.connect('database.db')
    sqlite_cursor = sqlite_conn.cursor()

    # Подключение к базе данных PostgreSQL
    postgres_conn = await asyncpg.connect(
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        database=os.environ["POSTGRES_DB"],
        host=os.getenv("DB_HOST", "postgres"),
        port=int(os.getenv("DB_PORT", "5432")),
    )

    try:
        # Получение данных из SQLite3 и их перенос в PostgreSQL
        sqlite_cursor.execute('SELECT telegram_id, first_name, username, words, added_at FROM user')
        rows = sqlite_cursor.fetchall()
        for row in rows:
            dt = datetime.datetime.strptime(row[-1], '%Y-%m-%d %H:%M:%S.%f')
            try:
                await postgres_conn.execute('''
                    INSERT INTO "user" (user_id, full_name, username, words, created_at, banned, active, last_active)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ''', *row[:-1], dt, False, True, None)
            except:
                continue

    finally:
        # Закрытие соединений
        await postgres_conn.close()
        sqlite_conn.close()

# Запуск асинхронной функции
asyncio.run(migrate_data())
