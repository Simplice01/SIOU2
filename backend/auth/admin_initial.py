from backend.models.user_model import User
from backend.core.database import get_db
from backend.core.security import hash_password
from sqlalchemy import select
import os 
from dotenv import load_dotenv
import asyncio
from backend.models.user_model import to_database_role

load_dotenv()


admin_username = os.getenv("USERNAME_ADMIN")
email_username = os.getenv("EMAIL_ADMIN")
password_admin = os.getenv("PASSWORD_ADMIN")
role_admin = os.getenv("ROLE")
first_name = os.getenv("FIRST_NAME")
last_name = os.getenv("LAST_NAME")

async def create_initial_admin():
    async for db in get_db():
        result = await db.execute(
            select(User).where(User._role == to_database_role("admin"))
        )

        admin = result.scalar_one_or_none()

        if admin is None:
            if password_admin is None:
                raise ValueError("Vérifier les infos des admins dans les variables d'environnement")
            admin = User(
                username=admin_username or email_username,
                first_name = first_name,
                last_name = last_name,
                password_hash=hash_password(password_admin),
                role=role_admin or "admin",
            )

            db.add(admin)
            await db.commit()
        break
    
if __name__ == "__main__":
    asyncio.run(create_initial_admin())
    
