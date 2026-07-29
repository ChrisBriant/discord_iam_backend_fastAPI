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

async def create_event(event_data):
    url = f"https://discord.com/api/v10/guilds/{guild_id}/scheduled-events"

    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json"
    }
    result = requests.post(url, headers=headers, json=event_data)

    if result.status_code == 200:
        data = result.json() 
        print("RESULT SUCCESSFUL", data)
        return data
    else:
        print("STATUS CODE", result.status_code, result.json(), url)
        raise APIRetrievalError("Unable to retrieve data from discord")

async def main():
    # events = await get_events()
    # print("EVENTS", events)
    # print("KEYS", events[0].keys())
    # for event in events:
    #     print("EVENT")
    #     for k, val in event.items():
    #         print(f"{k}: {val}")
    for i in range(0,5):
        fake_event = get_fake_event()
        print("THE FAKE EVENT IS", fake_event)
        channel_id = None
        entity_type = 3
        entity_metadata = None
        if fake_event["online"]:
            channel_id = "1393825603920199703"
            entity_type = 2
        else:
            entity_metadata = {"location": fake_event["location"]}
        fake_event_payload = {
            "name": fake_event["name"],
            "description" : fake_event["description"],
            "privacy_level": 2,
            "scheduled_start_time": fake_event["scheduled_start_time"],
            "scheduled_end_time": fake_event["scheduled_end_time"],
            "entity_type": entity_type,
            "channel_id" : channel_id,
            "entity_metadata" : entity_metadata
        }
        print("THE FAKE EVENT IS", fake_event_payload)
        try:
            await create_event(fake_event_payload)
        except Exception as e:
            print("ERROR", e)
        await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())