import asyncio

from sqlalchemy import text

from app.db.session import engine


async def check_database() -> None:
    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT 1"))
        print(f"Database connection OK: {result.scalar_one()}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check_database())
