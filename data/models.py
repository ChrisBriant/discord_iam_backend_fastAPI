from .db import Base, AsyncSession, SessionLocal
from typing import List
from sqlalchemy.exc import IntegrityError
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
    DateTime,
    func,
    Enum,
    select,
    delete,
    Boolean,
    update,
    Table,
    text
)
from sqlalchemy.orm import relationship, selectinload
import enum
import os, dotenv
from pathlib import Path
import json
import asyncio
import random
from datetime import datetime, timedelta, timezone
import secrets
#from services.auth_exceptions import TokenExpired, TokenNotFound, TokenUsed, DeviceAlreadyRegistered
#from services.auth import decode_public_key


class DatabaseUpdateError(Exception):
    pass



#
# Association Tables
#




#CUSTOM EXCEPTIONS

# class ManagerDoesNotExist(Exception):
#     pass

# class DepartmentDoesNotExist(Exception):
#     pass


#
# Role Model
#

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
)

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    discord_id = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False, unique=True)

    users = relationship(
        "User",
        secondary=user_roles,
        back_populates="roles",
    )


    @classmethod
    async def sync_user_roles(
        cls,
        db: AsyncSession,
        user: "User",
        discord_roles: list[dict],
    ):
        print("DISCORD ROLES", discord_roles)
        discord_ids = [r["discord_id"] for r in discord_roles]

        result = await db.execute(
            select(Role).where(Role.discord_id.in_(discord_ids))
        )
        existing_roles = result.scalars().all()

        role_lookup = {r.discord_id: r for r in existing_roles}

        assigned_roles = []

        for discord_role in discord_roles:

            role = role_lookup.get(discord_role["discord_id"])

            print("ROLE BEFORE INSERT", discord_role,role)

            if role is None:
                print("ROLE IS NONE")
                role = Role(
                    discord_id=discord_role["discord_id"],
                    name=discord_role["name"],
                )
                db.add(role)
                await db.flush()      # obtain primary key
                print("ROLE AFTER FLUSH", role.id, role.discord_id, role.name)
                role_lookup[role.discord_id] = role
                
            assigned_roles.append(role)
        print("ASSIGNED ROLES", assigned_roles)
        user.roles = assigned_roles
        print(
            "USER ROLES BEFORE RETURN",
            [r.name for r in user.roles]
        )
    # @classmethod
    # async def update_user_roles(cls,existing_user: User, discord_roles):
    #     for role in discord_roles:
    #         print(f"{existing_user.username} - ROLE", role)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    discord_id = Column(String, nullable=False, index=True, unique=True)
    user_name = Column(String, nullable=False, unique=True)
    global_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    terms_accepted = Column(Boolean, nullable=False, default=False)
    enabled = Column(Boolean, nullable=False, default=False)

    #
    # Roles
    #

    roles = relationship(
        "Role",
        secondary=user_roles,
        back_populates="users",
    )

    @classmethod
    async def create_one(
        cls,
        db: AsyncSession,
        discord_id : str,
        user_name: str,
        global_name : str | None,
        enabled: bool = True,
        roles : List | None = None,
        terms_accepted: bool = True,
    ) -> "User":

        #Process the roles
        user_roles = []

        for role_data in roles:
            result = await db.execute(
                select(Role).where(Role.discord_id == role_data["discord_id"])
            )
            role = result.scalar_one_or_none()

            if role is None:
                role = Role(
                    discord_id=role_data["discord_id"],
                    name=role_data["name"],
                )
                db.add(role)
                await db.flush()   # assigns PK without committing

            user_roles.append(role)

        user = cls(
            discord_id=discord_id,
            user_name=user_name,
            global_name=global_name,
            created_at=datetime.now(timezone.utc),
            roles = user_roles,
            enabled=enabled,
            terms_accepted=terms_accepted,
        )

        try:
            db.add(user)
            await db.commit()
            await db.flush()
            await db.refresh(user)
        except IntegrityError as ie:
            print("Error inserting user", ie)
            await db.rollback()
            #raise ValueError(ie._message)

        inserted_user = await db.execute(
            select(cls)
            .options(
                selectinload(cls.roles)
            )
        .where(cls.discord_id == discord_id))


        return inserted_user.scalar_one_or_none()

    # @staticmethod
    # async def update_roles(existing_user: "User", discord_roles):
    #     for role in discord_roles:
    #         print(f"{existing_user.user_name} - ROLE", role)


    @classmethod
    async def bulk_import(
        cls,
        db: AsyncSession,
        users: list[dict],
    ) -> dict:

        inserted = []
        existing = []
        failed = []

        for discord_user in users:

            try:
                existing_user = await db.execute(
                    select(cls)
                    .options(selectinload(User.roles))
                    .where(cls.discord_id == discord_user["id"])
                )

                existing_user = existing_user.scalar_one_or_none()

                if existing_user is not None:
                    existing.append(existing_user)
                    #Update roles if the existing user has changed roles
                    await Role.sync_user_roles(db,existing_user,discord_user["roles"])
                    continue

                user = await cls.create_one(
                    db,
                    discord_id=discord_user["id"],
                    user_name=discord_user["username"],
                    global_name=discord_user["global_name"],
                    roles=discord_user["roles"],
                )

                inserted.append(user)

            except Exception as ex:
                await db.rollback()
                failed.append({
                    "discord_id": discord_user["id"],
                    "error": str(ex)
                })

        await db.commit()
        return {
            "inserted": inserted,
            "existing": existing,
            "failed": failed,
        }

    @classmethod
    async def get_by_id(cls, db: AsyncSession, user_id: int):
        """
        Retrieve a user by ID with devices and tokens loaded.
        Returns the User object or None if not found.
        """
        result = await db.execute(
            select(cls)
            .options(
                selectinload(cls.department),
                selectinload(cls.manager),
                selectinload(cls.groups),
                selectinload(cls.roles)
            )
            .where(cls.id == user_id)
        )
        return result.scalar_one_or_none()
    
    @classmethod
    async def get_by_user_name(cls, db: AsyncSession, user_name: str):
        """
        Retrieve a user by username with devices and tokens loaded.
        Returns the User object or None if not found.
        """
        result = await db.execute(
            select(cls)
            .options(
                selectinload(cls.devices),
                selectinload(cls.tokens)
            )
            .where(cls.user_name == user_name)
        )
        return result.scalar_one_or_none()
    
    @classmethod
    async def get_random_user(cls, db: AsyncSession):
        """
        Retrieve a user by username with devices and tokens loaded.
        Returns the User object or None if not found.
        """
        result = await db.execute(
            select(cls)
            .options(
                selectinload(cls.department),
            )
            .order_by(func.random())
            .limit(1)
        )
        return result.scalar_one_or_none()


    @classmethod
    async def update_terms_accepted(cls, db: AsyncSession, user_id: int) :
        """
            Update the users table to accept the terms and conditions
        """
        try:

            update_stmt = update(cls).where(cls.id == int(user_id)).values(terms_accepted=True)
            await db.execute(update_stmt)
            await db.commit()
            # Fetch updated user
            result = await db.execute(
                select(cls).where(cls.id == int(user_id))
            )
            user = result.scalar_one_or_none()

            return user
        except Exception as e:
            # In a real application, you should log the error instead of just printing
            print(f"Error in update_terms_accepted: {e}")
            #Raise exception so that error propagates
            raise DatabaseUpdateError()   


    @classmethod
    async def enable_disable_user(cls, db: AsyncSession, user_id: int, enabled: bool) :
        """
            Enable or disable a user account
        """
        try:

            update_stmt = update(cls).where(cls.id == int(user_id)).values(enabled=enabled)
            await db.execute(update_stmt)
            await db.commit()
            # Fetch updated user
            result = await db.execute(
                select(cls).where(cls.id == int(user_id))
            )
            user = result.scalar_one_or_none()

            return user
        except Exception as e:
            # In a real application, you should log the error instead of just printing
            print(f"Error in enable_disable_user: {e}")
            #Raise exception so that error propagates
            raise DatabaseUpdateError()   

    @classmethod
    async def delete_by_id(
        cls,
        db: AsyncSession,
        id : int
    ):
        result = await db.execute(
            delete(cls).where(cls.id == id)
        )

        await db.commit()

        print("DELETE RESULT", result.rowcount)

        if result.rowcount > 0:
            return True
        else:
            return False

    @classmethod
    async def update_user(
        cls,
        db: AsyncSession,
        user_id: int,
        update_data: dict
    ) -> "User | None":
        """
            Partially update a user with only provided fields.
        """

        result = await db.execute(
            select(cls).where(cls.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None
        

        # apply only provided fields
        try:
            for key, value in update_data.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            await db.commit()
            await db.refresh(user)
        except IntegrityError as ie:
            await db.rollback()
            print("An error occurred updating the attribute", ie, key, value )
            error_detail = ie.orig.detail if hasattr(ie.orig, 'detail') else str(ie)
            raise Exception(error_detail)
        
        updated_user = await db.execute(
            select(cls)
            .options(
                selectinload(cls.roles),
            )
            .where(cls.id == user_id))
        return updated_user.scalar_one()





async def main():
    #print("Creating Departments")
    #await create_departments()
    print("Creating Users")
    await create_users(1)


if __name__ == "__main__":
    asyncio.run(main())