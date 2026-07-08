import dotenv, os, requests
from pathlib import Path


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


    if role_data.status_code == 200:
        #print("ROLE DATA", role_data.json())
        existing_roles = role_data.json()
        return [ {"id" : r['id'], "name" : r['name']} for r in existing_roles]
    else:
        raise APIRetrievalError

def get_members():

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
                "roles" : m["roles"] 
            }  for m in member_data
        ]
    else:
        raise APIRetrievalError


if __name__ == "__main__":
    try:
        existing_roles = get_roles()
        print("EXISTING ROLES", existing_roles)
    except APIRetrievalError as api_error:
        print("An error occurred retrieving the role data", api_error)

    try:
        existing_members = get_members()
        print("EXISTING MEMBERS", existing_members)
    except APIRetrievalError as api_error:
        print("An error occurred retrieving the member data", api_error)       