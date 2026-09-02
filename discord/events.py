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
from datetime import datetime, timezone
from asyncpg.exceptions import UniqueViolationError
from data.schemas import DBEvent
from fastapi import HTTPException

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

async def update_event(event_id, event_data):
    url = f"https://discord.com/api/v10/guilds/{guild_id}/scheduled-events/{event_id}"

    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json"
    }

    #Construct the event 
    location = None
    event_data_keys = event_data.keys()
    if "entity_type" in event_data_keys:
        print("ENTITY TYPE", event_data["entity_type"])
        if event_data["entity_type"] == 2:
            if "channel_id" not in event_data_keys:
                raise HTTPException(status_code=400,detail="Online events must include the channel id" )
        elif event_data["entity_type"] == 3:
            #THIS WILL NEED TO HAVE SOME VALIDATION FOR THE LOCATION IN FUTURE
            if not event_data["location"]:
                raise HTTPException(status_code=400,detail="Physical events must include a location" )
            location = event_data["location"]
        else:
            raise HTTPException(status_code=400,detail="Entity type must have a value of 2 (online) or 3 (physical)" )



    discord_payload = {
        "description": event_data.get("description"),
        "scheduled_end_time": event_data.get("start_time").isoformat() if event_data.get("start_time") else None,
        "entity_type": event_data.get("entity_type"),
        "name": event_data.get("name"),
        "start_time": event_data.get("end_time").isoformat() if event_data.get("end_time") else None,
        "channel_id": event_data.get("channel_id"),
        "entity_metadata" : {"location": location} if location else None
    }

    print("PAYLOAD", discord_payload)

    result = requests.patch(url, headers=headers, json=discord_payload)

    if result.status_code == 200:
        data = result.json()
        print("RESULT SUCCESSFUL", data)
        return data
    else:
        print("STATUS CODE", result.status_code, result.json(), url)
        raise APIRetrievalError(
            status_code=result.status_code,
            message=result.json()
        )

async def test_event_model():
    #TEST DATABASE EVENT FUNCTIONS
    test_event = {'id': '1542385039302463410', 'guild_id': '1393825603173744640', 'name': 'Stringy', 'description': 'string along with me', 'channel_id': None, 'creator_id': '1523518794746695710', 'image': None, 'scheduled_start_time': '2026-08-31T03:28:31.452000+00:00', 'scheduled_end_time': '2026-08-31T04:29:31.452000+00:00', 'status': 1, 'entity_type': 3, 'entity_id': None, 'recurrence_rule': None, 'privacy_level': 2, 'sku_ids': [], 'guild_scheduled_event_exceptions': [], 'entity_metadata': {'location': 'online'}}
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

async def update_event_in_db_from_discord_data(session,event_id,discord_data):
    try:
        print("USER",event_id,discord_data)
        user = await User.get_by_external_id(session,discord_data['creator']['id'])
        location = discord_data.get('entity_metadata', {}).get('location')
        channel_id = discord_data.get('channel_id')
        event = await Event.update_one(session,event_id,{
            "name" : discord_data["name"],
            "description" : discord_data["description"],
            "scheduled_start_time" : datetime.fromisoformat(discord_data["scheduled_start_time"]),
            "scheduled_end_time" : datetime.fromisoformat(discord_data["scheduled_end_time"]),
            "entity_type" : discord_data["entity_type"],
            "location"  : location,
            #"creator" : user,
            "channel_id" : channel_id,
        })
        return event
    except Exception as e:
        print("ERROR UPDATING FROM DISCORD DATA", e)

async def reconcile_events():
    """ 
        Retrieve the events from discord and reconcile them with the database
    """
    #await test_event_model()
    #TODO:
    # 1. Get the events from discord  
    discord_events = await get_events()
    discord_event_ids = [e['id'] for e in discord_events]
    # 2. Get the events from the database
    async with SessionLocal() as session: 
        db_events = await Event.get_all_from(session)
        db_event_ids = [e.discord_id for e in db_events]
        for db_event in db_events:
            if db_event.discord_id not in discord_event_ids:
                print("EVENT IS NOT ON DISCORD")
                # Check event exists in discord events if not set end date to current so that it has expired (later might be better to have an active or disabled column) 
                try:
                    await Event.update_one(session,db_event.id,{
                        "scheduled_start_time" : datetime.now(timezone.utc),
                    })
                except Exception as e:
                    print("ERROR", e)
        # 4. Iterate through each discord event - if event doesn't exist then add it
        for discord_event in discord_events:

            existing_event = await Event.get_by_discord_id(
                session,
                discord_event['id']
            )

            if existing_event:
                # Event exists in DB, regardless of whether it's past or future
                await update_event_in_db_from_discord_data(
                    session,
                    existing_event.id,
                    discord_event
                )

            else:
                # Event genuinely doesn't exist
                location = discord_event.get('entity_metadata', {}).get('location')

                user = await User.get_by_external_id(
                    session,
                    discord_event['creator']['id']
                )

                await Event.create_one(
                    session,
                    discord_event['id'],
                    discord_event['name'],
                    discord_event['description'],
                    datetime.fromisoformat(
                        discord_event['scheduled_start_time']
                    ),
                    discord_event["entity_type"],
                    user,
                    datetime.fromisoformat(
                        discord_event['scheduled_end_time']
                    ),
                    discord_event['channel_id'],
                    location
                )

        #PROBLEMS WITH FUTURE EVENTS BELOW
        # for discord_event in discord_events:
        #     #discord_start_time = datetime.fromisoformat(discord_event["scheduled_start_time"])
        #     #print("START TIMES", discord_start_time, datetime.now(timezone.utc))
        #     #db_event = [e for e in db_events if e.discord_id == discord_event['id'] ]
        #     #if len(db_event) < 1:
        #     if discord_event['id'] not in db_event_ids:  #and db_event.id > datetime.now(timezone.utc):
        #         print("DISCORD EVENT", discord_event['id'])
        #         #Get the creator from the DB
        #         location = discord_event.get('entity_metadata', {}).get('location')
        #         try:
        #             user = await User.get_by_external_id(session,discord_event['creator']['id'])
        #             print("USER",user)
        #         # except UniqueViolationError:
        #         #     print("EXISTS IN DATABASE")
        #         #     #Update the record
        #         except Exception as e:
        #             print("error", e)
        #         try:
        #             new_event = await Event.create_one(
        #                 session,
        #                 discord_event['id'],
        #                 discord_event['name'],
        #                 discord_event['description'],
        #                 datetime.fromisoformat(discord_event['scheduled_start_time']),
        #                 discord_event["entity_type"],  
        #                 user,
        #                 datetime.fromisoformat(discord_event['scheduled_end_time']),  
        #                 discord_event['channel_id'],
        #                 location     
        #             )
        #             if not new_event:
        #                 print("NEW EVENT NOT CREATED TRYING TO UPDATE IF EXISTING")
        #                 existing_event = await Event.get_by_discord_id(
        #                     session,
        #                     discord_event['id']
        #                 )
        #                 if existing_event:
        #                     await update_event_in_db_from_discord_data(session,existing_event.id,discord_event)
        #         except UniqueViolationError as uve:
        #             print("ERROR", uve)
        #             # existing_event = await Event.get_by_discord_id(
        #             #     session,
        #             #     discord_event['id']
        #             # )
        #             # await update_event_in_db_from_discord_data(session,existing_event.id,discord_event)
        #         except Exception as e:
        #             print("ERROR", e)

async def generate_fake_events():
    #GENERATE SOME FAKE EVENTS
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

async def main():
    # events = await get_events()
    # print("EVENTS", events)
    # print("KEYS", events[0].keys())
    # for event in events:
    #     print("EVENT")
    #     for k, val in event.items():
    #         print(f"{k}: {val}")

    #await generate_fake_events()

    #EVENT RECONCILIATION
    await reconcile_events()




if __name__ == "__main__":
    asyncio.run(main())