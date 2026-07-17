import os
import requests
from fastapi import HTTPException
from .base_provider import BaseProvider
from urllib.parse import urlencode


class DiscordProvider(BaseProvider):

    async def get_auth_url(self, state : str | None):
        base_url = "https://discord.com/oauth2/authorize"

        params = {
            "client_id": os.environ.get("CLIENT_ID_DISCORD"),
            "redirect_uri": f"{os.environ.get("BACKEND_REDIRECT_URI")}/auth/discord/callback",
            "response_type": "code",
            "scope": "openid email identify",
        }

        return f"{base_url}?{urlencode(params)}"

    async def exchange_code(self, code: str, state : str | None):
        url = "https://discord.com/api/oauth2/token"

        payload = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': f"{os.environ.get("BACKEND_REDIRECT_URI")}/auth/discord/callback"
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        CLIENT_SECRET = os.environ.get("CLIENT_SECRET_DISCORD")
        CLIENT_ID = os.environ.get("CLIENT_ID_DISCORD")

        response = requests.request("POST",url, data=payload, headers=headers, auth=(CLIENT_ID, CLIENT_SECRET))
        
        if response.status_code != 200:
            print("FAILED", response.text, payload)
            raise HTTPException(status_code=400, detail="An error occurred obtaining the token.")
        response_data =  response.json()
        return response_data['access_token']
        


 
        
    async def get_user_info(self, access_token: str):
        # 1. Define the API endpoint for the current user
        API_ENDPOINT = 'https://discord.com/api/v10/users/@me'
        
        # 2. Construct the Authorization header
        # NOTE: It is 'Bearer' for OAuth2 User Tokens and 'Bot' for Bot Tokens.
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        print(f"Attempting to validate token and fetch user data...")

        #Get the profile
        try:
            # 3. Make the GET request to the Discord API
            response = requests.get(API_ENDPOINT, headers=headers)
            
            # 4. Check the HTTP status code
            if response.status_code == 200:
                # Token is valid! Parse the JSON response.
                user_data = response.json()
                user_id = user_data.get('id')
                username = user_data.get('username')
                
                print("✅ Token is Valid.")
                print(f"User ID: {user_id}")
                print(f"Username: {username}")
                
                
            elif response.status_code == 401:
                # Token is invalid, expired, or revoked
                print("❌ Token is Invalid/Unauthorized (HTTP 401).")
                # Print the error details from the response for debugging
                print(f"Error Details: {response.text}")
                raise HTTPException(status_code=400, detail="An error occurred obtaining the profile.")
                
            else:
                # Handle other possible HTTP errors
                print(f"⚠️ API Request failed with status code: {response.status_code}")
                print(f"Error Details: {response.text}")
                raise HTTPException(status_code=response.status_code, detail="An error occurred obtaining the profile.")
        except Exception as e:
            print("AN ERROR OCCURRED VALIDATING THE TOKEN", e)
        return response.json()
    