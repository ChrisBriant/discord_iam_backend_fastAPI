import requests
import asyncio
import os
import sys
import dotenv
from pathlib import Path
from utils.exceptions import APIRetrievalError
from ai.events import get_fake_event
from data.models import Event, User
from data.db import SessionLocal
from datetime import datetime
from asyncpg.exceptions import UniqueViolationError
from data.schemas import DBEvent

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
        raise APIRetrievalError(status_code=result.status_code, message=result.json())

async def reconcile_events():
    """ 
        Retrieve the events from discord and reconcile them with the database
    """
    #TEST DATABASE EVENT FUNCTIONS
    test_event = {'id': '1542385039302463498', 'guild_id': '1393825603173744640', 'name': 'Stringy', 'description': 'string along with me', 'channel_id': None, 'creator_id': '1523518794746695710', 'image': None, 'scheduled_start_time': '2026-08-31T03:28:31.452000+00:00', 'scheduled_end_time': '2026-08-31T04:29:31.452000+00:00', 'status': 1, 'entity_type': 3, 'entity_id': None, 'recurrence_rule': None, 'privacy_level': 2, 'sku_ids': [], 'guild_scheduled_event_exceptions': [], 'entity_metadata': {'location': 'online'}}
    async with SessionLocal() as session:
        user = await User.get_by_id(session,1)
        try:
            event = await Event.create_one(
                session,
                test_event['id'],
                test_event['name'],
                test_event['description'],
                datetime.fromisoformat(test_event['scheduled_start_time']),
                test_event["entity_type"],  
                user,
                datetime.fromisoformat(test_event['scheduled_end_time']),  
                test_event['channel_id'],
                test_event['entity_metadata']['location']     
            )
        except UniqueViolationError as uve:
            print("ERROR", uve)
        except Exception as e:
            print("ERROR", e)
        #await Event.delete_by_id(session,2)
        event = await Event.get_by_id(session,3)
        
        #Update the event
        updated_event = None
        try:
            updated_event = await Event.update_one(session,3,{
                "name" : "Updated Event",
                "description" : "I am describing an updated event",
                "entity_type" : 2,
                "channel_id" : "1393825603920199703"
            })
        except Exception as e:
            print("ERROR", e)
        if updated_event: 
            event_response = DBEvent.model_validate(updated_event)
            print("EVENT", event_response.model_dump())

    #TODO:
    # 1. Get the events from the database
    # 2. Get the events from discord
    # 3. Iterate through each DB record
    #  A : Check event exists in discord events if not set end date to current so that it has expired (later might be better to have an active or disabled column) 
    #  B : Check details match apart from the location and the creator - update if not
    # 4. Iterate through each discord event - if event doesn't exist then add it

async def main():
    # events = await get_events()
    # print("EVENTS", events)
    # print("KEYS", events[0].keys())
    # for event in events:
    #     print("EVENT")
    #     for k, val in event.items():
    #         print(f"{k}: {val}")

    #EVENT RECONCILIATION
    await reconcile_events()

    #GENERATE SOME FAKE EVENTS
    # for i in range(0,5):
    #     fake_event = get_fake_event()
    #     print("THE FAKE EVENT IS", fake_event)
    #     channel_id = None
    #     entity_type = 3
    #     entity_metadata = None
    #     if fake_event["online"]:
    #         channel_id = "1393825603920199703"
    #         entity_type = 2
    #     else:
    #         entity_metadata = {"location": fake_event["location"]}
    #     fake_event_payload = {
    #         "name": fake_event["name"],
    #         "description" : fake_event["description"],
    #         "privacy_level": 2,
    #         "scheduled_start_time": fake_event["scheduled_start_time"],
    #         "scheduled_end_time": fake_event["scheduled_end_time"],
    #         "entity_type": entity_type,
    #         "channel_id" : channel_id,
    #         "entity_metadata" : entity_metadata
    #     }
    #     print("THE FAKE EVENT IS", fake_event_payload)
    #     try:
    #         await create_event(fake_event_payload)
    #     except Exception as e:
    #         print("ERROR", e)
    #     await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())