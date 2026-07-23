from fastapi import Depends, HTTPException
from authentication.token import validate_jwt
from data.models import User
from data.db import SessionLocal

#oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# async def get_current_user(
#     token: str = Depends(oauth2_scheme)
# ):
#     user_id = decode_token(token)

#     user = await db.get(User, user_id)

#     if not user:
#         raise HTTPException(
#             status_code=401,
#             detail="Invalid user"
#         )

#     return user

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
        print("USER ELIGIBLE ROLES", eligible_role_ids)
        if role_id in eligible_role_ids:
            #Get the role to return
            role = [eligible_role.role for eligible_role in user.eligible_roles_association if eligible_role.role_id == role_id ]
            print("USER AND ROLE", user, role[0])
            return {
                "user": user,
                "role": role[0],
            }
        raise HTTPException(status_code=403, detail=f"Not eligible for role activation")
        