from fastapi import Depends, HTTPException
from authentication.token import validate_jwt
from data.models import User, Event
from data.db import SessionLocal
from datetime import datetime, timezone
from typing import List

class EligibleRoleExpired(Exception):
    pass


class RequirePermission:
    def __init__(self, permission: str):
        self.permission = permission

    async def __call__(
        self,
        token_data = Depends(validate_jwt)
    ):
        print("REQUIRE PERMISSION", token_data)
        #Get the user from the database
        user = None
        async with SessionLocal() as session:
            user = await User.get_by_id(session,int(token_data["user_id"]))
            #user = await User.get_by_id(session,120)
        if not user:
            raise HTTPException(status_code=403, detail="User is not an authorised member")
        
        #Check user is enabled and accepted the terms and conditions
        if not user.terms_accepted:
            raise HTTPException(status_code=403, detail="Please accept the terms and conditions")
        
        if not user.enabled:
            raise HTTPException(status_code=403, detail="User is not enabled")
        
        #Check roles
        assigned_roles = [role.name for role in user.roles]
        if self.permission not in assigned_roles:
            raise HTTPException(status_code=403, detail=f"{self.permission} role is required")

        return user


class RequireRole:
    def __init__(self, roles: list[str]):
        self.roles = roles

    async def __call__(
        self,
        token_data = Depends(validate_jwt)
    ):
        """
            Requires one of the defined roles
        """
        #Get the user from the database
        user = None
        async with SessionLocal() as session:
            user = await User.get_by_id(session,int(token_data["user_id"]))
            #user = await User.get_by_id(session,120)
        if not user:
            raise HTTPException(status_code=403, detail="User is not an authorised member")
        
        #Check user is enabled and accepted the terms and conditions
        if not user.terms_accepted:
            raise HTTPException(status_code=403, detail="Please accept the terms and conditions")
        
        if not user.enabled:
            raise HTTPException(status_code=403, detail="User is not enabled")
        
        #Check roles
        assigned_roles = [role.name for role in user.roles]
        matching_roles = set(assigned_roles) & set(self.roles)
        if len(matching_roles) < 1:
            raise HTTPException(status_code=403, detail=f"A role in {self.roles} role is required")

        return user


async def get_authorised_user(token_data, roles):
    async with SessionLocal() as session:
        user = await User.get_by_id(
            session,
            int(token_data["user_id"])
        )

    if not user:
        raise HTTPException(
            status_code=403,
            detail="User is not an authorised member"
        )

    if not user.terms_accepted:
        raise HTTPException(
            status_code=403,
            detail="Please accept the terms and conditions"
        )

    if not user.enabled:
        raise HTTPException(
            status_code=403,
            detail="User is not enabled"
        )

    #Check roles
    assigned_roles = [role.name for role in user.roles]
    matching_roles = set(assigned_roles) & set(roles)
    if len(matching_roles) < 1:
        #User, but unauthorised for role
        return False, user
    #Authorised user
    return True, user


class RequireRoleOrOwner:
    def __init__(self, roles: list[str],object_type):
        self.roles = roles
        self.object_type = object_type
    async def __call__(
        self,
        object_id : int,
        token_data = Depends(validate_jwt)        
    ):
        authorised_for_role, user = await get_authorised_user(token_data, self.roles)
        if not authorised_for_role:
            async with SessionLocal() as session:
                try:
                    owner = await Event.get_owner(session,object_id)
                    if owner.id != user.id:
                        raise HTTPException(status_code=403,detail=f"Requires membership of {self.roles} or ownership of the object")
                except HTTPException:
                    raise
                except Exception as e:
                    print("ERROR", e)
                    raise HTTPException(status_code=400,detail="An error occurred retrieving the object from the database")

        return user   

class IsEligible:
    async def __call__(
        self,
        role_id : int,
        token_data = Depends(validate_jwt),
    ):
        #Get the user from the database
        user = None
        async with SessionLocal() as session:
            user = await User.get_by_id(session,int(token_data["user_id"]))
            #user = await User.get_by_id(session,120)
        if not user:
            raise HTTPException(status_code=403, detail="User is not an authorised member")

        eligible_role_ids = [eligible_role.role_id for eligible_role in user.eligible_roles_association]
        if role_id in eligible_role_ids:
            #Get the role to return
            eligible_role = [eligible_role for eligible_role in user.eligible_roles_association if eligible_role.role_id == role_id ][0]
            #Check the date to see that if it has expired
            if datetime.now(timezone.utc) > eligible_role.end_date:
                raise  HTTPException(status_code=403, detail=f"Eligible role has expired")
            print("USER AND ROLE", user, eligible_role.role)
            return {
                "user": user,
                "role": eligible_role.role,
            }
        raise HTTPException(status_code=403, detail=f"Not eligible for role activation")

class IsAssigned:
    async def __call__(
        self,
        role_id : int,
        token_data = Depends(validate_jwt),
    ):
        #Get the user from the database
        user = None
        async with SessionLocal() as session:
            user = await User.get_by_id(session,int(token_data["user_id"]))
            #user = await User.get_by_id(session,120)
        if not user:
            raise HTTPException(status_code=403, detail="User is not an authorised member")
        role_ids = [role.id for role in user.roles]
        if role_id in role_ids:
            #Get the role to return
            role = [role for role in user.roles if role.id == role_id ]
            print("USER AND ROLE", user, role[0])
            return {
                "user": user,
                "role": role[0],
            }
        raise HTTPException(status_code=404, detail="Role assignment not found")

class UserBasic:
    async def __call__(
        self,
        token_data = Depends(validate_jwt)
    ):
        """
            Returns a user for use when no permissions are required.
            This is for standard access
        """
        #Get the user from the database
        user = None
        async with SessionLocal() as session:
            user = await User.get_by_id(session,int(token_data["user_id"]))
            #user = await User.get_by_id(session,120)
        if not user:
            raise HTTPException(status_code=403, detail="User is not an authorised member")
        return user
        