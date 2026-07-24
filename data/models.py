from .db import Base, AsyncSession, SessionLocal
from typing import List
from sqlalchemy.exc import IntegrityError
from sqlalchemy import (
    Column,
    Integer,
    insert,
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

class DatabaseUpdateError(Exception):
    pass

class RoleNotFoundException(Exception):
    pass

class UserNotFoundException(Exception):
    pass


# Pure many-to-many helper table (no extra data columns, fine as a Table object)
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
)

# REFACTORED: Turned into an Association Object to support extra columns
class EligibleRole(Base):
    __tablename__ = "eligible_roles"

    user_id = Column(ForeignKey("users.id"), primary_key=True)
    role_id = Column(ForeignKey("roles.id"), primary_key=True)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)

    # Bidirectional relationships to the parent models
    user = relationship("User", back_populates="eligible_roles_association")
    role = relationship("Role", back_populates="eligible_users_association")


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    discord_id = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False, unique=True)

    # Standard Many-to-Many
    users = relationship(
        "User",
        secondary=user_roles,
        back_populates="roles",
    )

    # Refactored for Association Object
    eligible_users_association = relationship(
        "EligibleRole",
        back_populates="role",
        cascade="all, delete-orphan"
    )

    # Optional proxy property: lets you access Role objects directly via role.eligible_users
    # requires: from sqlalchemy.ext.associationproxy import association_proxy
    # eligible_users = association_proxy("eligible_users_association", "user")

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
        created_roles = []

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
            else:
                #Add new discord role
                role = Role(
                        discord_id=discord_role["discord_id"],
                        name=discord_role["name"],
                    )
                db.add(role)
                created_roles.append({
                    "discord_id": discord_role["discord_id"],
                    "name": discord_role["name"],
                })
                print ("DISCORD ROLE", discord_role,existing_roles)
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
        await db.commit()

        return {
            "renamed_roles": renamed_roles,
            "deleted_roles": deleted_roles,
            "created_roles" : created_roles
        }

    @classmethod
    async def get_by_id(cls, db: AsyncSession, role_id: int):
        """
        Retrieve a role by ID with devices and tokens loaded.
        Returns the role object or None if not found.
        """
        result = await db.execute(
            select(cls)
            .options(
                selectinload(cls.users),
                selectinload(cls.eligible_users_association),
            )
            .where(cls.id == role_id)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def get_all(cls, db: AsyncSession, page: int = 1 , page_size: int = 10):
        """
            Get all the roles
        """

        total_result = await db.execute(
            select(func.count()).select_from(cls)
        )
        total = total_result.scalar_one()

        #Get the paginated sessions
        offset = (page - 1) * page_size

        result = await db.execute(
            select(cls)
            .options(
                selectinload(cls.users),
                selectinload(cls.eligible_users_association).selectinload(EligibleRole.user)
            )
            .offset(offset)
            .limit(page_size)
        )

        return result.scalars().all(), total

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    discord_id = Column(String, nullable=False, index=True, unique=True)
    user_name = Column(String, nullable=False, unique=True)
    global_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    terms_accepted = Column(Boolean, nullable=False, default=False)
    enabled = Column(Boolean, nullable=False, default=False)

    # Standard Many-to-Many
    roles = relationship(
        "Role",
        secondary=user_roles,
        back_populates="users",
    )

    # Refactored for Association Object
    eligible_roles_association = relationship(
        "EligibleRole",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # Optional proxy property: lets you access Role objects directly via user.eligible_roles
    # requires: from sqlalchemy.ext.associationproxy import association_proxy
    # eligible_roles = association_proxy("eligible_roles_association", "role")

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
    async def remove_expired_roles(
        cls,
        db: AsyncSession,
        users: list[dict],
    ) -> dict:

        user_updated_roles = []
        user_updated_role_errors = []

        for discord_user in users:
            try:
                existing_user = await db.execute(
                    select(cls)
                    .options(
                        selectinload(User.roles),
                        selectinload(User.eligible_roles_association).selectinload(EligibleRole.role)
                    )
                    .where(cls.discord_id == discord_user["id"])
                )

                existing_user = existing_user.scalar_one_or_none()
                if existing_user is not None:
                    print("USER",existing_user.user_name)
                    #Check eligible roles against active roles
                    print("Active Roles", existing_user.roles)
                    #Filter the eligible roles
                    active_eligible_roles =  [ eligible_role.role for eligible_role in existing_user.eligible_roles_association if datetime.now(timezone.utc) < eligible_role.end_date ]
                    expired_eligible_roles = [ eligible_role.role for eligible_role in existing_user.eligible_roles_association if datetime.now(timezone.utc) > eligible_role.end_date ]
                    print("Eligible Roles", active_eligible_roles)
                    print("Expired eligible roles", expired_eligible_roles)
                    new_active_roles = [active_role for active_role in existing_user.roles if active_role in active_eligible_roles]
                    print("THESE ARE THE NEW ROLE ASSIGNMENTS", new_active_roles)
                    #Update the database
                    existing_user.roles = new_active_roles
                    #Report output
                    user_updated_roles.append({
                        "id" : existing_user.id,
                        "discord_id" : existing_user.discord_id,
                        "roles" : [ {
                            "id" : role.id,
                            "name" : role.name,
                            "discord_id" : role.discord_id
                        } for role in new_active_roles ]
                    })
                    

            except Exception as ex:
                user_updated_role_errors.append({
                    "id" : existing_user.id,
                    "discord_id" : existing_user.discord_id,
                    "error" : ex
                })
                print(f"Error processing user roles for {discord_user["username"]}, id= {discord_user["id"]}", ex)
        await db.commit()
        print("Results", user_updated_roles)
        print("Errors",user_updated_role_errors )
        return user_updated_roles, user_updated_role_errors 


    @classmethod
    async def bulk_import(
        cls,
        db: AsyncSession,
        users: list[dict],
    ) -> dict:
        """
            Imports new users only
        """
        inserted = []
        existing = []
        failed = []
        #new_roles_created = []

        for discord_user in users:

            try:
                existing_user = await db.execute(
                    select(cls)
                    .options(selectinload(User.roles))
                    .where(cls.discord_id == discord_user["id"])
                )

                existing_user = existing_user.scalar_one_or_none()

                #22/07/2026 - Skip role updates here as it is done using a different method
                # if existing_user is not None:
                #     #Update roles if the existing user has changed roles
                #     created_roles, role_changes = await Role.sync_user_roles(db,existing_user,discord_user["roles"])
                #     print("CREATED ROLES", created_roles)
                #     new_roles_created.extend(created_roles)
                #     existing.append({
                #         "user": existing_user.user_name,
                #         "role_changes": role_changes
                #     })
                #     continue

                if not existing_user:
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
            #"new roles" : new_roles_created,
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
            """
                Updates user attributes if they have changed on discord
            """
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
                selectinload(cls.eligible_roles_association).selectinload(EligibleRole.role)
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
    async def get_by_external_id(cls, db: AsyncSession, external_id: str):
        """
        Retrieve a user by the id provided by the 3rd party.
        """
        result = await db.execute(
            select(cls)
            # .options(
            #     selectinload(cls.devices),
            #     selectinload(cls.tokens)
            # )
            .where(cls.discord_id == external_id)
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
                selectinload(cls.eligible_roles_association).selectinload(EligibleRole.role)
            )
            .order_by(func.random())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def get_all_users(cls, db: AsyncSession, page: int = 1 , page_size: int = 10) :
        """
            Get all the users
        """

        total_result = await db.execute(
            select(func.count()).select_from(cls)
        )
        total = total_result.scalar_one()

        #Get the paginated sessions
        offset = (page - 1) * page_size

        result = await db.execute(
            select(cls)
            .options(
                selectinload(cls.roles),
                selectinload(cls.eligible_roles_association).selectinload(EligibleRole.role)
            )
            .offset(offset)
            .limit(page_size)
        )

        return result.scalars().all(), total


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
        role_id: int,
        start_date : datetime = datetime.now(),
        end_date : datetime = datetime.now() + timedelta(days=2),
    ) -> "User | None":
        """
            Make an eligible role assignment to a user 
            - update the database eligible roles table with the user id and role id
            - default the start date to the current date time
            - default the end date to one day in the future
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
        
        existing_eligible_roles = [ eligible_role.role for eligible_role in self.eligible_roles_association]

        if role not in existing_eligible_roles:
            #self.eligible_roles.append(role)
            print("I AM INSERTING AN ELIGIBLE ROLE", role, existing_eligible_roles)
            await db.execute(
                insert(EligibleRole).values(
                    user_id=self.id,
                    role_id=role_id,
                    start_date=start_date,
                    end_date=end_date
                )
            )
            db.expire(self, ['eligible_roles_association'])
        else:
            #Update the eligible role
            await db.execute(
                update(EligibleRole)
                .where(
                    EligibleRole.user_id == self.id,
                    EligibleRole.role_id == role_id
                )
                .values(
                    start_date=start_date,
                    end_date=end_date
                )
            )

        await db.flush()
        await db.commit()

        return self
    
    async def remove_eligible_role(
            self,
            db: AsyncSession,
            role_id: int
        ) -> "User":
            """
            Removes an eligible role assignment from a user.
            """
            # Find the specific eligibility record matching the role_id
            target_eligibility = None
            for eligibility in self.eligible_roles_association:
                if eligibility.role_id == role_id:
                    target_eligibility = eligibility
                    break

            # If it exists, remove it from the list. 
            # The 'delete-orphan' cascade deletes the row from the DB.
            if target_eligibility:
                self.eligible_roles_association.remove(target_eligibility)
                db.add(self)  # Track the change in the session
            else:
                raise RoleNotFoundException("The role could not be deleted because it could not be found")
                pass

            await db.commit()
            return self

    #NEEDS TO BE A CLASS METHOD - TAKE ROLE ID AND USER ID AS PARAMS
    @classmethod
    async def assign_role_as_active(
        cls,
        db: AsyncSession,
        role_id: int,
        user_id : int,
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
        #Get the user
        user_result = await db.execute(
            select(cls)
            .options(
                selectinload(cls.roles),
                selectinload(cls.eligible_roles_association).selectinload(EligibleRole.role)
            )
            .where(cls.id == user_id)
            .limit(1)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise UserNotFoundException()

        if role not in user.roles:
            user.roles.append(role)
            await db.flush()
        await db.commit()

        return user

    @classmethod
    async def remove_active_role(
        cls,
        db: AsyncSession,
        user_id: int,
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

        #Get the user
        user_result = await db.execute(
            select(cls)
            .options(
                selectinload(cls.roles),
                selectinload(cls.eligible_roles_association).selectinload(EligibleRole.role)
            )
            .where(cls.id == user_id)
            .limit(1)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise UserNotFoundException()

        if role in user.roles:
            user.roles.remove(role)

        await db.flush()
        await db.commit()

        return user
    
    # async def add_to_role(
    #     self,
    #     db: AsyncSession,
    #     role: Role
    # ):
    #     self.roles.append(role)
    #     print("ADDING ROLES", self.roles)
    #     await db.flush()
    #     await db.commit()
    


async def test_role_eligibility():
    async with SessionLocal() as session:
        user = await User.get_by_id(session,1)
        role = await Role.get_by_id(session,10)

        if user and role:
            print("USER",user.user_name)
            print("ROLE", role.name)
        else:
            print("User or Role not found")
            return

        print("ELIGIBLE ROLES")
        for eligible_role in user.eligible_roles_association:
            print(eligible_role.role.name)

        print("ACTIVE ROLES")
        for active_role in user.roles:
            print(active_role.name)

        #TEST ELIGIBLE ASSIGNMENT
        future_date = datetime.now() + timedelta(days=2)
        await user.assign_role_as_eligible(session,role.id,end_date=future_date)
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