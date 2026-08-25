import requests
import asyncio
import os
import sys
import dotenv
from pathlib import Path
from utils.exceptions import APIRetrievalError
from ai.events import get_fake_event

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

dotenv_file = PROJECT_ROOT / ".env"
files_dir = PROJECT_ROOT / "files"

if os.path.isfile(dotenv_file):
    dotenv.load_dotenv(dotenv_file)

bot_token = os.environ.get("DISCORD_BOT_TOKEN")
guild_id = os.environ.get("DISCORD_SERVER_ID")


async def kick_user(discord_id):
    url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{discord_id}"

    headers = {
        "Authorization": f"Bot {bot_token}"
    }
    result = requests.delete(url, headers=headers)

    if result.status_code == 204:
        print(result)
        return True

    result.raise_for_status()


async def main():
    try:
        response = await kick_user("1541636092728446996")
    except Exception as e:
        print("ERROR", e)
    print("KICKED", response)


if __name__ == "__main__":
    asyncio.run(main())