import dotenv, os, requests
from pathlib import Path
from data.models import User, Role
from data.db import SessionLocal
import asyncio
import logging
from sqlalchemy.exc import IntegrityError
from utils.formatting import format_reconciliation_log

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

dotenv_file = PROJECT_ROOT / ".env"
files_dir = PROJECT_ROOT / "files"

if os.path.isfile(dotenv_file):
    dotenv.load_dotenv(dotenv_file)

guild_id = os.environ.get("DISCORD_SERVER_ID")
bot_token = os.environ.get("DISCORD_BOT_TOKEN")

#For logging
log_directory = "/var/log/discord-iam"
os.makedirs(log_directory, exist_ok=True)

logger = logging.getLogger("iam")
logger.setLevel(logging.INFO)
handler = logging.FileHandler(
    f"{log_directory}/reconcile.log"
)
formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s"
)
handler.setFormatter(formatter)
logger.addHandler(handler)


#Custom exception
class APIRetrievalError(Exception):
    """Exception raised when an API data retrieval fails."""


def get_roles():
    #Get the roles
    url = f"https://discord.com/api/v10/guilds/{guild_id}/roles"

    headers = {
        "Authorization": f"Bot {bot_token}"
    }

    role_data = requests.get(url, headers=headers)

    print("ROLE DATA FROM API", role_data.status_code)


    if role_data.status_code == 200:
        #print("ROLE DATA", role_data.json())
        existing_roles = role_data.json()
        return [ {"discord_id" : r['id'], "name" : r['name']} for r in existing_roles]
    else:
        raise APIRetrievalError


def get_user_roles(user_discord_id):
    url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_discord_id}"

    headers = {
        "Authorization": f"Bot {bot_token}"
    }

    result = requests.get(url, headers=headers)

    if result.status_code == 200:
        data = result.json() 
        return data["roles"]
    else:
        print("STATUS CODE", result.status_code, result.json(), url)
        raise APIRetrievalError
    

def delete_user_role(user_discord_id,role_id):
    url = f"https://discord.com/api/v10//guilds/{guild_id}/members/{user_discord_id}/roles/{role_id}"

    headers = {
        "Authorization": f"Bot {bot_token}"
    }

    result = requests.delete(url, headers=headers)

    if result.status_code == 204: 
        return
    else:
        print("STATUS CODE", result.status_code, result.json(), url)
        raise APIRetrievalError("STATUS CODE", result.status_code, result.json(), url)

def add_user_role(user_discord_id,role_id):
    url = f"https://discord.com/api/v10//guilds/{guild_id}/members/{user_discord_id}/roles/{role_id}"

    headers = {
        "Authorization": f"Bot {bot_token}"
    }

    result = requests.put(url, headers=headers)

    if result.status_code == 204: 
        return
    else:
        print("STATUS CODE", result.status_code, result.json(), url)
        raise APIRetrievalError("STATUS CODE", result.status_code, result.json(), url)

def get_users():
    """
        Get all the users from discord and return the list
    """
    url = f"https://discord.com/api/v10/guilds/{guild_id}/members?limit=1000"
    headers = {
        "Authorization": f"Bot {bot_token}"
    }

    r = requests.get(url, headers=headers)

    if r.status_code == 200:
        user_data = r.json()

        return [ {
                "id" : u["user"]["id"], 
                "username" :  u["user"]["username"], 
                "global_name" :  u["user"]["global_name"],
                "roles": [
                    role_lookup[role_id]
                    for role_id in u["roles"]
                    if role_id in role_lookup
                ]
            }  for u in user_data
        ]
    else:
        print("STATUS CODE", r.status_code, r.json(), url)
        raise APIRetrievalError("STATUS CODE", r.status_code, r.json(), url)


def get_members(role_lookup):

    url = f"https://discord.com/api/v10/guilds/{guild_id}/members"

    headers = {
        "Authorization": f"Bot {bot_token}"
    }

    params = {
        "limit": 1000
    }

    r = requests.get(url, headers=headers, params=params)

    users = []

    if r.status_code == 200:
        member_data = r.json()

        return [ {
                "id" : m["user"]["id"], 
                "username" :  m["user"]["username"], 
                "global_name" :  m["user"]["global_name"],
                "roles": [
                    role_lookup[role_id]
                    for role_id in m["roles"]
                    if role_id in role_lookup
                ]
            }  for m in member_data
        ]
    else:
        raise APIRetrievalError

def update_role_membership(user_data):
    error_log = []
    success_log = []

    for discord_user in user_data:
        user_role_data = get_user_roles(discord_user["discord_id"])
        print("USER ROLE DATA", user_role_data)
        allowed_roles = [ role["discord_id"] for role in discord_user["roles"]]
        print("ALLOWED ROLES", allowed_roles)
        #Delete role assignments that are not allowed
        for discord_role in user_role_data:
            try:
                if discord_role not in allowed_roles:
                    delete_user_role(discord_user["discord_id"],discord_role)
                    success_log.append({
                        "discord_id" : discord_user["discord_id"],
                        "discord_role_id" : discord_role,
                        "status" : "DELETE" 
                    })
            except APIRetrievalError as err:
                error_log.append({
                    "discord_id" : discord_user["discord_id"],
                    "error" : err
                })
        #Add allowed role assignments
        for discord_role in allowed_roles:
            try:
                add_user_role(discord_user["discord_id"],discord_role)
                success_log.append({
                    "discord_id" : discord_user["discord_id"],
                    "discord_role_id" : discord_role,
                    "status" : "ASSIGNED" 
                })
            except APIRetrievalError as err:
                error_log.append({
                    "discord_id" : discord_user["discord_id"],
                    "error" : err
                })
        
    print("ERRORS", error_log)
    print("SUCCESS", success_log)
    return error_log, success_log


async def handle_bulk_import_reconciliation_to_db(user_data, role_data):

    async with SessionLocal() as session:
        #UPDATE ROLE ASSIGNMENTS BASED ON eligibility
        try:
            user_role_update_results, user_role_update_errors = await User.remove_expired_roles(session,user_data)
            # user_role_update_results = [{'id': 1, 'discord_id': '1065891826361434133', 'roles': [{'id': 10, 'name': 'User Manager', 'discord_id': '1526419413098561718'}]},
            #                             {'id': 1, 'discord_id': '1526484437724958760', 'roles': [{'id': 10, 'name': 'User Manager', 'discord_id': '1526419413098561718'}]}
            #                             ]
        except Exception as e:
            print("AN ERROR OCCURRED ON UPDATING ROLE ASSIGNMENTS", user_role_update_results)
        # UPDATE IN DISCORD
        errors, successes = update_role_membership(user_role_update_results)

        user_role_reconciliation_log = {
            "user_role_reconciliation" : {
                "successful_updates" : successes,
                "errors" : errors
            }
        }

        #BULK INSERT USERS
        user_update_results = None
        try:
            user_import_results = await User.bulk_import(session,user_data)
        except Exception as e:
            print("AN ERROR OCCURRED ON BULK UPDATE", user_update_results)

        if user_import_results:
            print("HERE IS THE RESULT OF THE LATEST IMPORT", user_import_results)

        #RECONCILIATION - BULK UPDATE USERS
        #Handle user name changes and users no longer on the discord server are disabled
        user_update_results = await User.bulk_reconcile(session,user_data)
        if user_update_results:
            print("USER RECONCILIATION RESULTS", user_update_results)

        #RECONCILIATION - BULK UPDATE ROLES
        role_update_results = None
        try:
            role_update_results = await Role.sync_roles(session,role_data)
            await session.commit()
        except Exception as e:
            print("AN ERROR OCCURRED ON BULK UPDATE", e)
        if role_update_results:
            print("ROLE SYNC REPORT", role_update_results)
        # #CREATE SERVER LOGS
        logger.info("User Role Updates = %s", user_role_reconciliation_log)
        logger.info("User Imports = %s", user_import_results)
        logger.info("User Changes = %s", user_update_results)
        logger.info("Role Updates = %s", role_update_results)


if __name__ == "__main__":
    try:
        existing_roles = get_roles()
        #print("EXISTING ROLES", existing_roles)
    except APIRetrievalError as api_error:
        print("An error occurred retrieving the role data", api_error)

    role_lookup = {
        role["discord_id"]: role
        for role in existing_roles
    }        

    existing_members = None

    try:
        #existing_members = get_members(role_lookup)
        existing_members = get_users()
        #print("EXISTING MEMBERS", existing_members)
    except APIRetrievalError as api_error:
        print("An error occurred retrieving the member data", api_error)       

    if existing_members:
        asyncio.run(handle_bulk_import_reconciliation_to_db(existing_members, existing_roles))
