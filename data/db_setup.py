import asyncio
from .db import engine, Base
from .models import User, Role
from sqlalchemy import text


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
        )

        
if __name__ == "__main__":
    asyncio.run(main())