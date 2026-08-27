from fastapi import APIRouter, HTTPException, Request, Depends, Response, Query, status
from datetime import datetime
from typing import Optional
from fastapi.responses import RedirectResponse, JSONResponse
from data.db import SessionLocal
from authorisation.permissions import RequirePermission, RequireRole, IsEligible, IsAssigned, UserBasic
from data.schemas import (
    DiscordChannelMessage,
    DiscordUserProfile,
    DiscordEvent,
    DiscordInputEvent,
    Channel,
)
from typing import List
#import bleach
from discord.feed import get_messages, get_channels as get_channels_from_discord
from discord.events import get_events, create_event
from utils.exceptions import APIRetrievalError


router = APIRouter()

@router.get("/channels/messages/{channel_id}", response_model=List[DiscordChannelMessage])
async def get_channel_messages(
        channel_id : str
    ):
    """
        Get messages by channel id
    """
    messages = []
    try:
        messages = await get_messages(channel_id)
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Unable to retrieve messages")
    messages_response = [
        DiscordChannelMessage(
            id=m['id'],
            channel_id=m['channel_id'],
            content=m['content'],
            date_created=m['timestamp'],
            date_modified=m['edited_timestamp'],
            author=DiscordUserProfile(
                discord_id = m['author']['id'],
                user_name = m['author']['username'],
                global_name=m['author']['global_name'],
                #bot = m['author'].get("bot"),
            ),
            type=int(m['type'])
        )
        for m in messages 
    ]
    print(messages_response)
    return messages_response


@router.get("/events", response_model=List[DiscordEvent])
async def get_events_route(

    ):
    """
        Get the events from discord
    """
    events = []
    try:
        events = await get_events()
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Unable to retrieve events")
    print("EVENTS LENGTH", len(events))
    events_response = [
        DiscordEvent(
            id=e['id'],
            channel_id=e['channel_id'],
            name=e['name'],
            description=e['description'],
            start_time=e['scheduled_start_time'],
            end_time=e['scheduled_end_time'],
            creator=DiscordUserProfile(
                discord_id = e['creator']['id'],
                user_name = e['creator']['username'],
                global_name=e['creator']['global_name'],
            ),
            entity_type=int(e['entity_type'])
        )
        for e in events
    ]
    return events_response

@router.get("/channels", response_model=List[Channel])
async def get_channels():
    try:
        channel_data = await get_channels_from_discord()
        print("CHANNEL DATA", channel_data)
    except Exception as e:
        raise HTTPException(status_code=400,detail="Unable to retrieve channel data" )
    response_data = [ Channel.model_validate(c) for c in channel_data]
    # for c in channel_data:
    #     print("DATA")
    #     print(c["parent_id"])
    # response_data = [ Channel(
    #                     id = c["id"],
    #                     name = c["name"],
    #                     parent_id = c["parent_id"]
    #                 ) for c in channel_data]
    return response_data


#TODO : Investigate a way to obtain the user's discord token for creating the events as the signed in user
@router.post("/events", response_model= DiscordEvent)
async def post_event_route(
        event : DiscordInputEvent,
        user = Depends(RequirePermission("Event Administrator"))
    ):
    """
        Creates a new event
    """

    location = event.location

    if event.entity_type == 2:
        #Must have a chanel ID
        if not event.channel_id:
            raise HTTPException(status_code=400,detail="Channel ID is required for online events" )
    elif event.entity_type == 3:
        #Must have a location
        if not event.location:
            raise HTTPException(status_code=400,detail="Location is required for physical events" )
        
    else:
        raise HTTPException(status_code=400,detail="Invalid entity type" )
        
    event_payload = {
        "name": event.name,
        "description" : event.description,
        "privacy_level": 2,
        "scheduled_start_time": event.start_time.isoformat() if event.start_time is not None else None,
        "scheduled_end_time": event.end_time.isoformat() if event.end_time is not None else None,
        "entity_type": event.entity_type, #online = 2, physical = 3
        "channel_id" : event.channel_id,
        "entity_metadata" : {"location": location} if location is not None else None
    }
    try:
        new_event = await create_event(event_payload)
        if not new_event:
            raise HTTPException(status_code=400,detail="Unable to create event" )

        #new_event = {'id': '1542385039302463498', 'guild_id': '1393825603173744640', 'name': 'Stringy', 'description': 'string along with me', 'channel_id': None, 'creator_id': '1523518794746695710', 'image': None, 'scheduled_start_time': '2026-08-31T03:28:31.452000+00:00', 'scheduled_end_time': '2026-08-31T04:29:31.452000+00:00', 'status': 1, 'entity_type': 3, 'entity_id': None, 'recurrence_rule': None, 'privacy_level': 2, 'sku_ids': [], 'guild_scheduled_event_exceptions': [], 'entity_metadata': {'location': 'online'}}

        event_response = DiscordEvent(
            id = new_event['id'],
            name = new_event['name'],
            description = new_event['name'],
            channel_id = new_event['channel_id'],
            entity_type = new_event['entity_type'],
            start_time = datetime.fromisoformat(new_event['scheduled_start_time']),
            end_time= datetime.fromisoformat(new_event['scheduled_end_time']) if new_event['scheduled_end_time'] is not None else None,
            creator = DiscordUserProfile(
                    discord_id = user.discord_id,
                    user_name = user.user_name,
                    global_name = user.global_name
            )
        )
        return event_response
    except APIRetrievalError as api_err:
        print("API ERROR",api_err, api_err.status_code)
        raise HTTPException(status_code=api_err.status_code,detail=api_err.message )
    except Exception as e:
        print("ERROR", e) 

#TODO : Create the endpoint code for modifying an event
@router.patch("/events", response_model= DiscordEvent)
async def change_event_route(
    event : DiscordInputEvent,
    user = Depends(RequireRole(["User Manager","Role Manager"]))
):
    return ("Hello Alex")