from pydantic import BaseModel, ConfigDict, computed_field
from typing import Optional
from datetime import datetime
from typing import List, TypeVar, Optional, Generic

T = TypeVar("T")


class TokenSchema(BaseModel):
    access_token: str
    refresh_token: str

class ProviderSchema(BaseModel):
    id : str
    name : str
    logo : str
    login : str

class UserProfileSchema(BaseModel):
    id : int
    idp : str
    alias : str
    accepted_terms : bool

class RoleSchema(BaseModel):
    id : int
    discord_id : str
    name : str

    model_config = ConfigDict(from_attributes=True)

class EligibleRoleSchema(BaseModel):
    #id : int
    # discord_id : str
    # name : str
    role : RoleSchema
    start_date : datetime
    end_date : datetime

    model_config = ConfigDict(from_attributes=True)

class UserSchema(BaseModel):
    id: int
    discord_id: str
    user_name : str
    global_name : str | None = None
    created_at : datetime
    terms_accepted : bool
    enabled : bool
    roles : List[RoleSchema]
    eligible_roles_association : List[EligibleRoleSchema]

    model_config = ConfigDict(from_attributes=True)

# class UserList(BaseModel):
#     users : List[UserSchema]

class AuthCodeSchema(BaseModel):
    auth_code : str

class RefreshTokenSchema(BaseModel):
    token : str | None


class PaginatedResponse(BaseModel, Generic[T]):
    data: List[T]
    next_page: Optional[str]
    prev_page: Optional[str]
    total: int
    total_pages: int
    page: int
    page_size: int