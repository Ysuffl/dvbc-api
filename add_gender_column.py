
import asyncio
from sqlalchemy import text
from app.db.session import engine

async def add_gender_column():
    async with engine.begin() as conn:
        # Check if column exists
        result = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='customers' AND column_name='gender'"))
        if not result.fetchone():
            print("Adding gender column to customers table...")
            await conn.execute(text("ALTER TABLE customers ADD COLUMN gender VARCHAR(20)"))
            print("Column added successfully.")
        else:
            print("Gender column already exists.")

if __name__ == "__main__":
    asyncio.run(add_gender_column())
