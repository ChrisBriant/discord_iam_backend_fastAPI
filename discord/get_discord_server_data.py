import dotenv, os, requests
from pathlib import Path
from data.models import User, Role
from data.db import SessionLocal
import asyncio
from sqlalchemy.exc import IntegrityError

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

dotenv_file = PROJECT_ROOT / ".env"
files_dir = PROJECT_ROOT / "files"

if os.path.isfile(dotenv_file):
    dotenv.load_dotenv(dotenv_file)

guild_id = os.environ.get("DISCORD_SERVER_ID")
bot_token = os.environ.get("DISCORD_BOT_TOKEN")

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

async def handle_bulk_import_reconciliation_to_db(user_data, role_data):

    async with SessionLocal() as session:
        user_update_results = None
        #BULK INSERT USERS
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
        #INSERT ONE BY ONE
        # for discord_user in user_data:
        #     exsiting_or_inserted_user = None

        #     try:
        #         await User.create_one(
        #             session,
        #             discord_user['id'], 
        #             discord_user['username'],
        #             discord_user['global_name'],
        #             roles= discord_user['roles']
        #         )
        #     except Exception as e:
        #         print("DAABASE ERROR", e)

        #print("INSERTED OR EXISTING USER", exsiting_or_inserted_user)

# async def update_roles_to_db(role_data):
#     async with SessionLocal() as session:
#         role_update_results = None
#         #BULK UPDATE
#         try:
#             role_update_results = await Role.sync_roles(session,role_data)
#             session.commit()
#         except Exception as e:
#             print("AN ERROR OCCURRED ON BULK UPDATE", e)
#         if role_update_results:
#             print("ROLE SYNC REPORT", role_update_results)

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
        existing_members = get_members(role_lookup)
        #print("EXISTING MEMBERS", existing_members)
    except APIRetrievalError as api_error:
        print("An error occurred retrieving the member data", api_error)       

    if existing_members:
        asyncio.run(handle_bulk_import_reconciliation_to_db(existing_members, existing_roles))
