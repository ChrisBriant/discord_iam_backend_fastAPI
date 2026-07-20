from fastapi import APIRouter, HTTPException, Request, Depends, Response, Query, status
from typing import Optional
from fastapi.responses import RedirectResponse
from providers.provider_registry import get_provider
# from data.db_actions import (
#     get_or_add_user, 
#     get_user, 
#     get_feedback,
#     create_auth_code,
#     validate_auth_code,
#     update_terms_accepted,
# )
from data.models import User, Role, RoleNotFoundException
from data.db import SessionLocal
import uuid
from authentication.token import (
    obtain_jwt_pair, 
    refresh_jwt_pair, 
    validate_jwt_token, 
    validate_jwt_cookie,
    validate_jwt, 
    RefreshTokenExpiredError, 
    InvalidRefreshTokenError,
    ACCESS_TOKEN_LIFETIME,
    REFRESH_TOKEN_LIFETIME
)
from authorisation.permissions import RequirePermission
from data.schemas import (
    PaginatedResponse,
    UserSchema,
    #EligibleRoleSchema,
    RoleSchemaWithUsers,
    RoleAssignmentSchema
)
from math import ceil
from typing import List
from pathlib import Path
import json
import os
#import bleach
import base64

router = APIRouter()

###
#USER (Discord Member) MANAGEMENT ENDPOINTS
###


@router.get("/users", response_model=PaginatedResponse)
async def get_users(
        request: Request,
        user = Depends(RequirePermission("User Manager")),
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=100)
    ):
    """
        Check that the user is authorised and then retrieve all users
    """

    #Get the users
    async with SessionLocal() as session:
        all_users, total_users = await User.get_all_users(
            session,
            page,
            page_size
        )

        all_users_result = [UserSchema.model_validate(u) for u in all_users ]

        total_pages = ceil(total_users / page_size)

        #Build next page URL
        next_page: Optional[str] = None
        if len(all_users) == page_size:
            next_page = str(
                request.url.include_query_params(
                    page=page + 1,
                    page_size=page_size
                )
            )
        prev_page: Optional[str] = None
        if page > 0:
            prev_page = str(
                request.url.include_query_params(
                    page=page - 1,
                    page_size=page_size
                )
            )     

        return {
            "data": all_users_result,
            "next_page": next_page,
            "prev_page" : prev_page,
            "total": total_users,
            "total_pages": total_pages,
            "page": page,
            "page_size": page_size
        }


@router.get("/roles", response_model=PaginatedResponse)
async def get_roles(
        request: Request,
        user = Depends(RequirePermission("User Manager")),
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=100)
    ):
    """
        Check that the user is authorised and then retrieve all roles
    """
    #Get the users
    async with SessionLocal() as session:
        all_roles, total_roles = await Role.get_all(
            session,
            page,
            page_size
        )

        for role in all_roles:
            print("ROLE ", role.id, role.eligible_users_association)
            all_roles_result = [RoleSchemaWithUsers.model_validate(u) for u in all_roles ]

            

        total_pages = ceil(total_roles / page_size)

        #Build next page URL
        next_page: Optional[str] = None
        if len(all_roles) == page_size:
            next_page = str(
                request.url.include_query_params(
                    page=page + 1,
                    page_size=page_size
                )
            )
        prev_page: Optional[str] = None
        if page > 0:
            prev_page = str(
                request.url.include_query_params(
                    page=page - 1,
                    page_size=page_size
                )
            )     

        return {
            "data": all_roles_result,
            "next_page": next_page,
            "prev_page" : prev_page,
            "total": total_roles,
            "total_pages": total_pages,
            "page": page,
            "page_size": page_size
        }
    

@router.post("/setroleaseligible", dependencies=[Depends(RequirePermission("User Manager"))], status_code=status.HTTP_201_CREATED)
async def set_eligible_role_association(
        #request: Request,
        role_assignment : RoleAssignmentSchema,
    ):
    print(role_assignment.role_id, role_assignment.user_id)
    async with SessionLocal() as session:
        #Get the user
        user = None
        try:
            user = await User.get_by_id(session,user_id=role_assignment.user_id)
            await user.assign_role_as_eligible(session,role_assignment.role_id,start_date=role_assignment.start_date,end_date=role_assignment.end_date)
        except RoleNotFoundException as role_ex:
            raise HTTPException(status_code=404, detail="Role does not exist")
        except Exception as e:
            print("Error", e)
            if not user:
                raise HTTPException(status_code=404, detail="User does not exist")
        #TO DO - Needs to return an updated user object
    return {"status": "success", "message": "Role assignment completed"}


@router.post("/removeeligiblerole", dependencies=[Depends(RequirePermission("User Manager"))], status_code=status.HTTP_201_CREATED)
async def remove_eligible_role_association(
        role_assignment : RoleAssignmentSchema,
    ):
    print(role_assignment.role_id, role_assignment.user_id)
    async with SessionLocal() as session:
        #Get the user
        try:
            user = await User.get_by_id(session,user_id=role_assignment.user_id)
            await user.remove_eligible_role(session,role_assignment.role_id)
        except RoleNotFoundException as role_ex:
            raise HTTPException(status_code=404, detail="Role does not exist")
        except Exception as e:
            if not user:
                raise HTTPException(status_code=404, detail="User does not exist")
        #TO DO - Needs to return an updated user object
    return {"status": "success", "message": "Role assignment completed"}



# @router.post("/activaterole", status_code=status.HTTP_201_CREATED)
# async def activate_eligible_role(
#     role_id : int,
#     user = Depends(IsEligble("User Manager"))
# ):
#     """
#         Check the role is eligible and set as an active role if so.
#     """
#     #TODO - Role reconciliation needs to remove expired role assignments
#     pass


# @router.post("/updateroleassignment", status_code=status.HTTP_201_CREATED)
# async def update_eligible_role(
#     role_assignment : RoleAssignmentSchema,
#     user = Depends(IsEligble("User Manager"))
# ):
    """
        Update the eligible role assignment
    """