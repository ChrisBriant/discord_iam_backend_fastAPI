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
    TokenSchema, 
    ProviderSchema, 
    UserProfileSchema, 
    AuthCodeSchema,
    RefreshTokenSchema,
)
from typing import List
from pathlib import Path
import json
import os
#import bleach
import base64

router = APIRouter()


@router.get("/users", response_model=str)
async def get_users(user = Depends(RequirePermission("User Manager"))):

    print("TOKEN DATA", user)
    #Get the users

    return "hello"