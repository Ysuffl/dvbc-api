"""
Migration script: Add age, total_spending, master_level to customers table in PostgreSQL.
Run once via: python3 add_customer_fields.py
"""
import asyncio
import asyncpg
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/beach_club_db"
)

# Convert to asyncpg DSN (strip SQLAlchemy prefix)
PG_DSN = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def run():
    conn = await asyncpg.connect(PG_DSN)

    existing = await conn.fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_name='customers'"
    )
    existing_cols = {row["column_name"] for row in existing}

    migrations = []
    if "age" not in existing_cols:
        migrations.append("ALTER TABLE customers ADD COLUMN age INTEGER DEFAULT NULL")
    if "total_spending" not in existing_cols:
        migrations.append("ALTER TABLE customers ADD COLUMN total_spending FLOAT DEFAULT 0.0")
    if "master_level" not in existing_cols:
        migrations.append("ALTER TABLE customers ADD COLUMN master_level VARCHAR(20) DEFAULT 'Bronze'")

    if not migrations:
        print("✅ All columns already exist. Nothing to migrate.")
        await conn.close()
        return

    for sql in migrations:
        print(f"Running: {sql}")
        await conn.execute(sql)

    await conn.close()
    print("✅ Migration complete.")


if __name__ == "__main__":
    asyncio.run(run())
