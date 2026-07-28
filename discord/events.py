import requests
import asyncio
import os
import sys
import dotenv
from pathlib import Path
from utils.exceptions import APIRetrievalError

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

dotenv_file = PROJECT_ROOT / ".env"
files_dir = PROJECT_ROOT / "files"

if os.path.isfile(dotenv_file):
    dotenv.load_dotenv(dotenv_file)

bot_token = os.environ.get("DISCORD_BOT_TOKEN")
guild_id = os.environ.get("DISCORD_SERVER_ID")

async def get_events():
    url = f"https://discord.com/api/v10/guilds/{guild_id}/scheduled-events"

    headers = {
        "Authorization": f"Bot {bot_token}"
    }
    result = requests.get(url, headers=headers)

    if result.status_code == 200:
        data = result.json() 
        return data
    else:
        print("STATUS CODE", result.status_code, result.json(), url)
        raise APIRetrievalError("Unable to retrieve data from discord")


async def main():
    events = await get_events()
    print("EVENTS", events)
    print("KEYS", events[0].keys())
    for event in events:
        print("EVENT")
        for k, val in event.items():
            print(f"{k}: {val}")

if __name__ == "__main__":
    asyncio.run(main())