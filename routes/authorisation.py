from fastapi import APIRouter, HTTPException, Request, Depends, Response, Query
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
from data.models import User
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
    UserSchema
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

    print("TOKEN DATA", user)
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

    