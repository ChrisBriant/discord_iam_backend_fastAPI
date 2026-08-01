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
        raise APIRetrievalError("Unable to retrieve data")


async def get_channels():
    url = f"https://discord.com/api/v10/guilds/{guild_id}/channels"

    headers = {
        "Authorization": f"Bot {bot_token}"
    }
    result = requests.get(url, headers=headers)

    if result.status_code == 200:
        data = result.json()
        #Filter so that you only get text and voice channels
        filtered_data = [ ch for ch in data if ch["type"] in [0,2] ]
        return filtered_data
    else:
        print("STATUS CODE", result.status_code, result.json(), url)
        raise APIRetrievalError("Unable to retrieve data")


async def main(channel_id):
    # discord_messages = None
    # try:
    #     discord_messages = await get_messages(channel_id)
    # except Exception as e:
    #     print("Error", e)
    # if discord_messages:
    #     print("These are the discord message keys", discord_messages[0].keys())
    #     for message in discord_messages:
    #         #print("MESSAGE DATA", message.keys())
    #         print("CONTENT", message['id'], message['author'], message["content"], message["type"])
    channels = await get_channels()
    if channels:
        for channel in channels:
            print("CHANNEL", channel)



if __name__ == "__main__":
    channel_id = None
    if len(sys.argv) > 1:
        channel_id = sys.argv[1]
    asyncio.run(main(channel_id))

    #asyncio.run(get_channels())