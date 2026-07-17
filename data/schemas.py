from pydantic import BaseModel, ConfigDict, computed_field
from typing import Optional
from datetime import datetime
from typing import List


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

class UserSchema(BaseModel):
    id: int
    alias: str

    model_config = ConfigDict(from_attributes=True)

class AuthCodeSchema(BaseModel):
    auth_code : str

class RefreshTokenSchema(BaseModel):
    token : str | None
