import requests
import asyncio
import os
import sys
import dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

dotenv_file = PROJECT_ROOT / ".env"
files_dir = PROJECT_ROOT / "files"

if os.path.isfile(dotenv_file):
    dotenv.load_dotenv(dotenv_file)

bot_token = os.environ.get("DISCORD_BOT_TOKEN")

async def get_messages(channel_id):
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"

    headers = {
        "Authorization": f"Bot {bot_token}"
    }
    result = requests.get(url, headers=headers)

    if result.status_code == 200:
        data = result.json() 
        return data
    else:
        print("STATUS CODE", result.status_code, result.json(), url)
        raise Exception #APIRetrievalError


async def main(channel_id):
    discord_messages = await get_messages(channel_id)
    #print("These are the discord messages", discord_messages)
    for message in discord_messages:
        #print("MESSAGE DATA", message.keys())
        print("CONTENT", message["content"])

if __name__ == "__main__":
    channel_id = sys.argv[1]
    asyncio.run(main(channel_id))