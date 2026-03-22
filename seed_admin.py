import asyncio
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.core.security import get_password_hash
from sqlalchemy.future import select

async def seed_admin():
    async with SessionLocal() as db:
        stmt = select(User).where(User.username == "admin")
        result = await db.execute(stmt)
        admin = result.scalars().first()
        if not admin:
            hashed_pw = get_password_hash("admin123")
            admin_user = User(
                username="admin",
                hashed_password=hashed_pw,
                role=UserRole.ADMIN,
                is_active=True
            )
            db.add(admin_user)
            await db.commit()
            print("Admin user seeded successfully (admin/admin123)!")
        else:
            print("Admin user already exists.")

if __name__ == "__main__":
    asyncio.run(seed_admin())
