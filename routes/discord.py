from fastapi import APIRouter, HTTPException, Request, Depends, Response, Query, status
from typing import Optional
from fastapi.responses import RedirectResponse, JSONResponse
from data.db import SessionLocal
from authorisation.permissions import RequirePermission, IsEligible, IsAssigned, UserBasic
from data.schemas import (
    DiscordChannelMessage,
    DiscordUserProfile,
    DiscordEvent,
    Channel,
)
from typing import List
#import bleach
from discord.feed import get_messages, get_channels as get_channels_from_discord
from discord.events import get_events


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




#TODO : Create an endpoint to create events if the user has permission