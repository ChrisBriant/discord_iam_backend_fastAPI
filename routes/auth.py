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
from .token import (
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

# Go to project root (adjust parents[n] if needed)
PROJECT_ROOT = Path(__file__).resolve().parents[1]

ALLOWED_REDIRECTS = [
    "uk.chrisbriant.idbroker://callback", "http://localhost:5173/",
]


@router.get("/providers", response_model = List[ProviderSchema])
async def get_providers():
    """
        Helper which lists the providers with a media link and login link.
        It reads from the providers.json file and creates the response object
    """

    providers_path = PROJECT_ROOT / "providers" / "providers.json"

    with open(providers_path, "r", encoding="utf-8") as f:
        providers = json.load(f)

    provider_list = [ ProviderSchema(
        id=p['id'], 
        name=p['name'],
        logo= f"{os.environ.get("BACKEND_REDIRECT_URI")}{p['logo']}",
        login= f"{os.environ.get("BACKEND_REDIRECT_URI")}/auth/{p['id']}/login"
    ) for p in providers]
    return provider_list

@router.get("/{provider}/login")
async def login(provider: str,redirect_uri: str | None = Query(None),set_cookie : bool = Query(True)):
    """
        Performs the login to the IDP using their authorisation endpoint. It then redirects to the token exchange endpoint.
        Example: https://localhost:8000/auth/linkedin/login
    """

    idp = get_provider(provider)

    # Generate secure state
   
    if(redirect_uri):
        print("REDIRECT URI", redirect_uri)
        #Check on allowed redirects list
        if redirect_uri not in ALLOWED_REDIRECTS :
            print("REDIRECT NOT AUTHORIZED")
            return RedirectResponse(f"{redirect_uri}?error=unauthorised")

    #The redirect uri is encoded in the state data, this is for redirects from different clients, e.g. android, web
    state_data = {
        "csrf": str(uuid.uuid4()),
        "redirect_uri": redirect_uri,
        "set_cookie" : set_cookie
    }
    state = base64.urlsafe_b64encode(json.dumps(state_data).encode()).decode()

    auth_url = await idp.get_auth_url(state)

    print("AUTH URL", auth_url)

    # Redirect browser immediately
    response = RedirectResponse(auth_url)

    # Store state in a cookie
    response.set_cookie(
        key=f"oauth_state_{provider}",
        value=state,
        httponly=True,
        secure=True,
        samesite="none"
    )

    return response


@router.get("/{provider}/callback", response_model=str)
async def auth_callback_with_redirect(request: Request, provider: str, code: str, state: str | None = Query(None)):
    """
        Handles the callback from the IDP
        1. Takes the code from the payload and exchanges it for a token
        2. The token is verified and the user profile data returned
        3. User profile data is stored in the database
        4. JWT token is issued and set within the session cookie
    """

    idp = get_provider(provider)

    #Handle the state if it is in the payload
    stored_state = request.cookies.get(f"oauth_state_{provider}")
    if state:
        print("STATES", stored_state, state)
        if stored_state != state:
            raise HTTPException(status_code=401,detail="Invalid state")
    #Check for redirect URI in stored_state
    state_data = json.loads(base64.urlsafe_b64decode(stored_state).decode())
    redirect_uri = state_data.get("redirect_uri")
    set_cookie = state_data.get("set_cookie")
    print("REDIRECT URI IS ", redirect_uri, set_cookie)

    #State is passed in as some providers need to pass it to the token endpoint
    access_token = await idp.exchange_code(code, state)

    #Verify the token and return the user profile data
    user_profile = await idp.get_user_info(access_token)

    # database logic here
    async with SessionLocal() as session:
        user_record = await User.get_by_external_id(session,str(user_profile["id"]))
        if not user_record:
            raise HTTPException(
                status_code=400,
                detail="Failed to create the user"
            )
    print("USER RECORD BEFORE ISSUE JWT", user_record)
    #Issue a JWT
    jwt_token_pair = obtain_jwt_pair(str(user_record.id),"discord", user_record.user_name, user_record.terms_accepted) 
 
    #Set the redirect URI depending on whether it exists in the cookie set to default if not in cookie
    response_redirect_uri = redirect_uri if redirect_uri else os.environ.get("CLIENT_REDIRECT_URI")

    #Divert flow depending on whether delivering tokens in cookie or sending auth code
    if set_cookie:
        response = RedirectResponse(
            url=response_redirect_uri,
            status_code=302
        )
        # Access token cookie
        response.set_cookie(
            key="access_token",
            value=jwt_token_pair["access"],
            httponly=True,
            secure=True,          # HTTPS only
            samesite="none",
            max_age=ACCESS_TOKEN_LIFETIME,
        )

        # Refresh token cookie
        response.set_cookie(
            key="refresh_token",
            value=jwt_token_pair["refresh"],
            httponly=True,
            secure=True,
            samesite="none",
            max_age=REFRESH_TOKEN_LIFETIME, 
        )
    #MOBILE FLOW NOT USED FOR NOW
    # else :
    #     #Generate an auth code
    #     auth_code = await create_auth_code(user_record["id"])
    #     response = RedirectResponse(
    #         url= f"{response_redirect_uri}?code={auth_code.code}",
    #         status_code=302
    #     )

    return response

@router.get("/session", response_model=UserProfileSchema)
async def get_session(token_data = Depends(validate_jwt)):
    response = UserProfileSchema(
        id=token_data["user_id"],
        idp= token_data["idp"],
        accepted_terms = token_data["accepted_terms"],
        alias=token_data["alias"]
    )
    return response

@router.post("/acceptterms", response_model=UserProfileSchema)
async def accept_terms(response: Response, set_cookie : bool = Query(True), token_data = Depends(validate_jwt)):
    """
        Accepts the terms and conditions in the database and then updates the token
    """
    try:
        await User.update_terms_accepted()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Unable to update the terms and conditions.")
    
    #Issue a new JWT with the updated accepted terms
    jwt_token_pair = obtain_jwt_pair(token_data["user_id"], token_data["idp"], token_data["alias"], True)
    
    # Set new cookies
    if set_cookie:
        response.set_cookie(
            key="access_token",
            value=jwt_token_pair["access"],
            httponly=True,
            secure=True,
            samesite="none",
            max_age=ACCESS_TOKEN_LIFETIME
        )

        response.set_cookie(
            key="refresh_token",
            value=jwt_token_pair["refresh"],
            httponly=True,
            secure=True,
            samesite="none",
            max_age=REFRESH_TOKEN_LIFETIME
        )

    return UserProfileSchema(
        id=token_data["user_id"],
        idp= token_data["idp"],
        accepted_terms = True,
        alias=token_data["alias"]
    )


@router.post("/logout")
def logout(response: Response):
    """
        Logs out the user by clearing the Cookies
    """
    response.delete_cookie(
        key="access_token",
        path="/",
        secure=True,
        samesite="none",
    )

    response.delete_cookie(
        key="refresh_token",
        path="/",
        secure=True,
        samesite="none",
    )
    return {"status": "logged_out"}


@router.post("/refresh")
async def refresh_jwt(request: Request, response: Response, refresh: Optional[RefreshTokenSchema], set_cookie : bool = Query(True)):
    """
        Takes the refresh token and issues a new token pair and sets the session cookie
    """

    # Fallback to cookie (browser clients)
    if not refresh.token:
        print("HERE")
        refresh_token = request.cookies.get("refresh_token")
    else:
        print("GETTING REFRESH TOKEN")
        refresh_token = refresh.token
    try:
        jwt_token_pair = refresh_jwt_pair(refresh_token)

    except RefreshTokenExpiredError as e:
        print("Refresh token expired", e)
        raise HTTPException(status_code=401, detail="Refresh token expired")

    except InvalidRefreshTokenError as e:
        print("Refresh token invalid", e)
        raise HTTPException(status_code=401, detail="Refresh token invalid")

    # Set new cookies
    if set_cookie:
        response.set_cookie(
            key="access_token",
            value=jwt_token_pair["access"],
            httponly=True,
            secure=True,
            samesite="none",
            max_age=ACCESS_TOKEN_LIFETIME
        )

        response.set_cookie(
            key="refresh_token",
            value=jwt_token_pair["refresh"],
            httponly=True,
            secure=True,
            samesite="none",
            max_age=REFRESH_TOKEN_LIFETIME
        )

        return {"status": "refreshed"}
    
    token_pair = TokenSchema(
        access_token = jwt_token_pair['access'],
        refresh_token = jwt_token_pair['refresh'], 
    )

    return token_pair

# @router.post("/exchangeauthcodeforjwt", response_model=TokenSchema)
# async def exchange_auth_code_for_jwt(auth_code : AuthCodeSchema):
#     """
#         This endpoint is called by the client to exchange an auth code for a JWT token and return the response as Json
#         This is designed to support authorisation flows where there isn't an option of setting an authorisaton cookie
#     """
#     #Get the user from the database if the code is valid
#     user = await validate_auth_code(auth_code.auth_code)
#     if not user:
#         raise HTTPException(status_code=401,detail="Authorisation code is invalid")
    
#     jwt_token_pair = obtain_jwt_pair(user.id, user.idp, user.alias, user.terms_accepted)

#     response = TokenSchema(
#         access_token = jwt_token_pair['access'],
#         refresh_token = jwt_token_pair['refresh'],
#     )

#     return response

@router.get("/testredirect")
def test_mobile_redirect():
    """
        Test redirection to the scheme
    """    
    response = RedirectResponse(
        url="uk.chrisbriant.pairauth://pair?token=abc123",
        status_code=302
    )
    return response