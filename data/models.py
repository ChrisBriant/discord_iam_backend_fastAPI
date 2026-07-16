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

class RoleNotFoundException(Exception):
    pass

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

eligible_roles = Table(
    "eligible_roles",
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

    eligible_users = relationship(
        "User",
        secondary=eligible_roles,
        back_populates="eligible_roles",
    )


    @classmethod
    async def sync_user_roles(
        cls,
        db: AsyncSession,
        user: "User",
        discord_roles: list[dict],
    ):
        #For reporting
        created_roles = []
        added_roles = []
        removed_roles = []

        discord_ids = [r["discord_id"] for r in discord_roles]

        result = await db.execute(
            select(Role).where(Role.discord_id.in_(discord_ids))
        )
        existing_roles = result.scalars().all()

        role_lookup = {r.discord_id: r for r in existing_roles}

        assigned_roles = []

        for discord_role in discord_roles:

            role = role_lookup.get(discord_role["discord_id"])

            if role is None:
                role = Role(
                    discord_id=discord_role["discord_id"],
                    name=discord_role["name"],
                )
                db.add(role)
                await db.flush()      # obtain primary key
                #For logging
                created_roles.append(role.name)
                #For lookup on susequent users
                role_lookup[role.discord_id] = role
                
            assigned_roles.append(role)
        #For logging the role updates
        existing_role_names = {
            role.name
            for role in user.roles
        }
        new_role_names = {
            role.name
            for role in assigned_roles
        }
        added_roles = list(new_role_names - existing_role_names)
        removed_roles = list(existing_role_names - new_role_names)
        
        user.roles = assigned_roles
        return created_roles, {
            "added_roles": added_roles,
            "removed_roles": removed_roles,
        }


    @classmethod
    async def sync_roles(
        cls,
        db: AsyncSession,
        discord_roles: list[dict],
    ) -> dict:

        renamed_roles = []
        deleted_roles = []

        # Get all roles currently in database
        result = await db.execute(
            select(cls)
            .options(selectinload(cls.users))
        )

        existing_roles = result.scalars().all()

        existing_lookup = {
            role.discord_id: role
            for role in existing_roles
        }

        discord_role_ids = {
            role["discord_id"]
            for role in discord_roles
        }

        # Check roles that still exist in Discord
        for discord_role in discord_roles:

            existing_role = existing_lookup.get(
                discord_role["discord_id"]
            )

            if existing_role:

                if existing_role.name != discord_role["name"]:
                    renamed_roles.append({
                        "discord_id": existing_role.discord_id,
                        "old_name": existing_role.name,
                        "new_name": discord_role["name"],
                    })

                    existing_role.name = discord_role["name"]


        # Find roles removed from Discord
        for existing_role in existing_roles:

            if existing_role.discord_id not in discord_role_ids:

                deleted_roles.append({
                    "discord_id": existing_role.discord_id,
                    "name": existing_role.name,
                })

                # Delete the role
                await db.delete(existing_role)


        await db.flush()

        return {
            "renamed_roles": renamed_roles,
            "deleted_roles": deleted_roles,
        }

    @classmethod
    async def get_by_id(cls, db: AsyncSession, role_id: int):
        """
        Retrieve a user by ID with devices and tokens loaded.
        Returns the User object or None if not found.
        """
        result = await db.execute(
            select(cls)
            .options(
                selectinload(cls.users),
                selectinload(cls.eligible_users),
            )
            .where(cls.id == role_id)
        )
        return result.scalar_one_or_none()


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

    eligible_roles = relationship(
        "Role",
        secondary=eligible_roles,
        back_populates="eligible_users",
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
        new_roles_created = []

        for discord_user in users:

            try:
                existing_user = await db.execute(
                    select(cls)
                    .options(selectinload(User.roles))
                    .where(cls.discord_id == discord_user["id"])
                )

                existing_user = existing_user.scalar_one_or_none()

                if existing_user is not None:
                    #Update roles if the existing user has changed roles
                    created_roles, role_changes = await Role.sync_user_roles(db,existing_user,discord_user["roles"])
                    print("CREATED ROLES", created_roles)
                    new_roles_created.extend(created_roles)
                    existing.append({
                        "user": existing_user.user_name,
                        "role_changes": role_changes
                    })
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
            "new roles" : new_roles_created,
        }

    @classmethod
    async def bulk_reconcile(
        cls,
        db: AsyncSession,
        users: list[dict],
    ) -> dict:

        updated = []
        disabled = []
        failed = []

        try:
            # Create lookup from Discord response
            discord_users = {
                user["id"]: user
                for user in users
            }
            # Get all users from database
            result = await db.execute(
                select(cls)
            )
            database_users = result.scalars().all()

            for db_user in database_users:
                discord_user = discord_users.get(db_user.discord_id)
                #
                # User exists in Discord
                #
                if discord_user:
                    changes = {}

                    if db_user.user_name != discord_user["username"]:
                        changes["user_name"] = {
                            "old": db_user.user_name,
                            "new": discord_user["username"]
                        }
                        db_user.user_name = discord_user["username"]

                    if db_user.global_name != discord_user["global_name"]:
                        changes["global_name"] = {
                            "old": db_user.global_name,
                            "new": discord_user["global_name"]
                        }
                        db_user.global_name = discord_user["global_name"]

                    if not db_user.enabled:
                        changes["enabled"] = {
                            "old": False,
                            "new": True
                        }
                        db_user.enabled = True

                    if changes:
                        updated.append({
                            "discord_id": db_user.discord_id,
                            "changes": changes
                        })
                #
                # User no longer exists in Discord
                #
                else:
                    if db_user.enabled:
                        db_user.enabled = False

                        disabled.append({
                            "discord_id": db_user.discord_id,
                            "username": db_user.user_name
                        })

            await db.commit()

        except Exception as ex:
            await db.rollback()

            failed.append({
                "error": str(ex)
            })

        return {
            "updated": updated,
            "disabled": disabled,
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
                selectinload(cls.roles),
                selectinload(cls.eligible_roles)
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
                selectinload(cls.roles),
                selectinload(cls.eligible_roles)
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

    async def assign_role_as_eligible(
        self,
        db: AsyncSession,
        role_id: int
    ) -> "User | None":
        """
            Make an eligible role assignment to a user 
            - update the database eligible roles table with the user id and role id
        """
        #Get the role
        role_result = await db.execute(
            select(Role)
            .where(Role.id == role_id)
            .limit(1)
        )
        role = role_result.scalar_one_or_none()
        if not role:
            raise RoleNotFoundException()

        if role not in self.eligible_roles:
            self.eligible_roles.append(role)

        await db.flush()
        await db.commit()

        return self
    
    async def remove_eligible_role(
        self,
        db: AsyncSession,
        role_id: int
    ) -> "User | None":
        """
            Make an eligible role assignment to a user 
            - update the database eligible roles table with the user id and role id
        """
        #Get the role
        role_result = await db.execute(
            select(Role)
            .where(Role.id == role_id)
            .limit(1)
        )
        role = role_result.scalar_one_or_none()
        if not role:
            raise RoleNotFoundException()

        if role in self.eligible_roles:
            self.eligible_roles.remove(role)

        await db.flush()
        await db.commit()

        return self

    async def assign_role_as_active(
        self,
        db: AsyncSession,
        role_id: int
    ) -> "User | None":
        """
            Make an eligible role assignment to a user 
            - update the database eligible roles table with the user id and role id
        """
        #Get the role
        role_result = await db.execute(
            select(Role)
            .where(Role.id == role_id)
            .limit(1)
        )
        role = role_result.scalar_one_or_none()
        if not role:
            raise RoleNotFoundException()

        if role not in self.roles:
            self.roles.append(role)

        await db.flush()
        await db.commit()

        return self
    
    async def remove_active_role(
        self,
        db: AsyncSession,
        role_id: int
    ) -> "User | None":
        """
            Make an eligible role assignment to a user 
            - update the database eligible roles table with the user id and role id
        """
        #Get the role
        role_result = await db.execute(
            select(Role)
            .where(Role.id == role_id)
            .limit(1)
        )
        role = role_result.scalar_one_or_none()
        if not role:
            raise RoleNotFoundException()

        if role in self.roles:
            self.roles.remove(role)

        await db.flush()
        await db.commit()

        return self


async def test_role_eligibility():
    async with SessionLocal() as session:
        user = await User.get_by_id(session,6)
        role = await Role.get_by_id(session,10)

        if user and role:
            print("USER",user.user_name)
            print("ROLE", role.name)
        else:
            print("User or Role not found")
            return

        print("ELIGIBLE ROLES")
        for eligible_role in user.eligible_roles:
            print(eligible_role.name)

        print("ACTIVE ROLES")
        for active_role in user.roles:
            print(active_role.name)

        #TEST ELIGIBLE ASSIGNMENT
        #await user.assign_role_as_eligible(session,role.id)
        #TEST REMOVE ELIGIBLE ROLE
        #await user.remove_eligible_role(session,role.id)
        #TEST ASSIGN ACTIVE
        #await user.assign_role_as_active(session,role.id)
        #TEST REMOVE ACTIVE
        #await user.remove_active_role(session,role.id)







async def main():
    #TESTING ROLE ELIGIBILITY
    await test_role_eligibility()


if __name__ == "__main__":
    asyncio.run(main())