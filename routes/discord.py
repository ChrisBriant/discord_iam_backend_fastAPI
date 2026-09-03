from fastapi import APIRouter, HTTPException, Request, Depends, Response, Query, status
from datetime import datetime
from typing import Optional
from fastapi.responses import RedirectResponse, JSONResponse
from data.db import SessionLocal
from authorisation.permissions import (
    RequirePermission, 
    RequireRole,
    RequireRoleOrOwner, 
    IsEligible, 
    IsAssigned, 
    UserBasic
)
from data.schemas import (
    DiscordChannelMessage,
    DiscordUserProfile,
    DiscordEvent,
    DBEvent,
    DiscordInputEvent,
    DBEvent,
    Channel,
)
from typing import List
#import bleach
from discord.feed import get_messages, get_channels as get_channels_from_discord
from discord.events import get_events, create_event, update_event, update_event_in_db_from_discord_data
from utils.exceptions import APIRetrievalError
from data.models import Event
from math import ceil
from sqlalchemy.exc import IntegrityError

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


@router.get("/events/discord", response_model=List[DiscordEvent])
async def get_events_discord_route(

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

@router.get("/events",) # response_model=List[DiscordEvent])
async def get_events_db_route(
        request : Request,
        page : int = 1,
        page_size : int = 10,
        paginate : bool = False,
    ):

    async with SessionLocal() as session:
        if not paginate:
            events = await Event.get_all_from(session)
            all_events_result = [DBEvent.model_validate(e) for e in events]
            return events 
        else:
            paginated_events, total_users = await Event.get_all_paginated(
                session,
                page,
                page_size
            )

        all_events_result = [DBEvent.model_validate(e) for e in paginated_events ]

        total_pages = ceil(total_users / page_size)

        #Build next page URL
        next_page: Optional[str] = None
        if len(paginated_events) == page_size:
            next_page = str(
                request.url.include_query_params(
                    page=page + 1,
                    page_size=page_size
                )
            )
        prev_page: Optional[str] = None
        if page > 0:
            prev_page = str(
                request.url.include_query_params(
                    page=page - 1,
                    page_size=page_size
                )
            )     

        return {
            "data": all_events_result,
            "next_page": next_page,
            "prev_page" : prev_page,
            "total": total_users,
            "total_pages": total_pages,
            "page": page,
            "page_size": page_size
        }


@router.get("/events/{event_id}", response_model=DBEvent)
async def get_event_db_route(
        event_id : int
    ):
    """
        Get a single event
    """
    async with SessionLocal() as session:
        try:
            print("FETCHING EVENT")
            event = await Event.get_by_id(session,int(event_id))
            if not event:
                raise HTTPException(status_code=404,detail="Event not found" )
            print("DUMPED EVENT", event)
            print(event.__dict__)
            event_response = DBEvent.model_validate(event)
            return event_response
        except Exception as e:
            print("ERROR", e)
            raise HTTPException(status_code=400,detail="Unable to retrieve event" )
    

# @router.get("/events/{event_id}", response_model=List[DiscordEvent])
# async def get_events_db_route(
#         event_id : int
#     ):
#     """
#         Get a single event
#     """
#     async with SessionLocal as session:
#         event = Event.get_by_id()
#     return None



@router.patch("/events/{event_id}", response_model= DBEvent)
async def modify_event_route(
        event_id : int,
        event_data : DiscordInputEvent,
        user = Depends(RequireRole(["Event Administrator", "Event Manager"]))
    ):
    """
        Modify an event
    """
    #GET THE EVENT FIRST
    async with SessionLocal() as session:
        try:
            db_event = await Event.get_by_id(session,event_id) 
            if not db_event:
                raise HTTPException(status_code=404,detail="Event not found" )
            
        except Exception as e:
            print("EVENT TO UPDATE", e)
            raise HTTPException(status_code=400,detail="An error occurred retrieving the event" )
        #UPDATE IN DISCORD FIRST AND THEN UPDATE DATABASE
        
        try:
            updated_discord_event = await update_event(db_event.discord_id,event_data.model_dump())
        except APIRetrievalError as api_error:
            print("Error", api_error)
            raise HTTPException(status_code=400,detail="An error occurred updating discord")
        except HTTPException as http_e:
            print("An error occurred updating discord", http_e)
            raise http_e
        except Exception as e:
            raise HTTPException(status_code=400,detail="An error occurred updating discord")
        print("UPDATED THE EVENT IN DISCORD", updated_discord_event)
        #DOESN'T UPDATE PROPERLY IN THE DATABASE - NEED TO LOOK AT WHY IT IS FAILING ON CREATOR OR IF IT IS EVEN
        #CREATOR SHOULD NOT BE REQUIRED
        #updated_db_event = await update_event_in_db_from_discord_data(session,event_id,updated_discord_event)
        location = updated_discord_event.get('entity_metadata', {}).get('location')
        updated_db_event = await Event.update_one(session,event_id,{
            "name" : updated_discord_event["name"],
            "description" : updated_discord_event["description"],
            "scheduled_start_time" : datetime.fromisoformat(updated_discord_event["scheduled_start_time"]),
            "scheduled_end_time" : datetime.fromisoformat(updated_discord_event["scheduled_end_time"]),
            "entity_type" : updated_discord_event["entity_type"],
            "location"  : location,
            "channel_id" : updated_discord_event["channel_id"],
        })
        print("UPDATED IN DB", updated_db_event)
        response = DBEvent.model_validate(updated_db_event)
    return response


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
#   CHANGE TO DBEvent and return the event from the database after updating it from discord
@router.post("/events", response_model = DBEvent)
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
        # if not new_event:
        #     raise HTTPException(status_code=400,detail="Unable to create event" )

        #new_event = {'id': '1542385039302463498', 'guild_id': '1393825603173744640', 'name': 'Stringy', 'description': 'string along with me', 'channel_id': None, 'creator_id': '1523518794746695710', 'image': None, 'scheduled_start_time': '2026-08-31T03:28:31.452000+00:00', 'scheduled_end_time': '2026-08-31T04:29:31.452000+00:00', 'status': 1, 'entity_type': 3, 'entity_id': None, 'recurrence_rule': None, 'privacy_level': 2, 'sku_ids': [], 'guild_scheduled_event_exceptions': [], 'entity_metadata': {'location': 'online'}}

        # event_response = DiscordEvent(
        #     id = new_event['id'],
        #     name = new_event['name'],
        #     description = new_event['name'],
        #     channel_id = new_event['channel_id'],
        #     entity_type = new_event['entity_type'],
        #     start_time = datetime.fromisoformat(new_event['scheduled_start_time']),
        #     end_time= datetime.fromisoformat(new_event['scheduled_end_time']) if new_event['scheduled_end_time'] is not None else None,
        #     creator = DiscordUserProfile(
        #             discord_id = user.discord_id,
        #             user_name = user.user_name,
        #             global_name = user.global_name
        #     )
        # )
        # CODE FAILING HERE
        #new_event = {'id': '1543830560282116139', 'guild_id': '1393825603173744640', 'name': 'Meeting for the sake of meeting', 'description': 'Join this this evening for a pointless evening.', 'channel_id': '1393825603920199703', 'creator_id': '1523518794746695710', 'image': None, 'scheduled_start_time': '2026-10-14T19:30:00+00:00', 'scheduled_end_time': '2026-10-14T20:30:00+00:00', 'status': 1, 'entity_type': 2, 'entity_id': None, 'recurrence_rule': None, 'privacy_level': 2, 'sku_ids': [], 'guild_scheduled_event_exceptions': [], 'entity_metadata': {}}
        #print("DISCORD EVENT", event_response.json_dump())
        location = new_event.get('entity_metadata', {}).get('location')
        
        #Add the event to the database
        print("FAILING WITH LOCATION", location)
        async with SessionLocal() as session:
            try:
                print("UPDATING THE DB")
                db_event = await Event.create_one(
                    session,
                    new_event['id'],
                    new_event['name'],
                    new_event['description'],
                    datetime.fromisoformat(
                        new_event['scheduled_start_time']
                    ),
                    new_event["entity_type"],
                    user,
                    datetime.fromisoformat(
                        new_event['scheduled_end_time']
                    ),
                    new_event['channel_id'],
                    location
                )
                #THIS IS WHERE THE FAILURE IS HAPPENING - I THINK
                print("DB EVENT?", db_event)
                if not db_event:
                    raise HTTPException(status_code=400,detail="Event already exists" )
            except Exception as e:
                print("Error inserting new event", db_event)
                #Should have code to roll back the created event in discord
                raise HTTPException(status_code=400,detail="Unable to add the new event to the database" )
            event_response = DBEvent.model_validate(db_event)
            print("EVENT RESPONSE", event_response)
            return event_response
    except APIRetrievalError as api_err:
        print("API ERROR",api_err, api_err.status_code)
        raise HTTPException(status_code=api_err.status_code,detail=api_err.message )
    except Exception as e:
        print("ERROR", e) 

#TODO : Create the endpoint code for deleting an event
@router.delete("/events/{object_id}", response_model= str) #DBEvent)
async def delete_event_route(
    user = Depends(RequireRoleOrOwner(["Event Administrator"],object_type = Event)),
):
    """
        delete an event
    """
    print("USER", user)
    #Get the event
    #1. Delete on discord
    #2. Delete on the database
    return ("Hello Alex")

@router.delete("/events/{event_id}/creator", response_model= str) #DBEvent)
async def change_event_organiser_route(
    event : DiscordInputEvent,
    user = Depends(RequireRole(["Event Administrator","Creator"]))
):
    """
        Change the creator on an event
    """
    #1. Update in the database, needs database method
    return ("Hello Alex")