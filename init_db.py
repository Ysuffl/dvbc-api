import asyncio
from app.db.session import engine
from app.db.base import Base
# import models to register them
from app.models.table_booking import Table, Booking, Customer
from app.models.user import User

async def init_db():
    async with engine.begin() as conn:
        print("Dropping existing tables...")
        await conn.run_sync(Base.metadata.drop_all)
        print("Creating new tables...")
        await conn.run_sync(Base.metadata.create_all)
    print("Database reset completed successfully!")

if __name__ == "__main__":
    asyncio.run(init_db())
