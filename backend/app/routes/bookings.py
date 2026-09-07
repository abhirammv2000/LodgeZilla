from fastapi import APIRouter, Body, Depends, HTTPException, Query
import pymongo

from ..db import listing_collection, push_to_redis, user_collection
from .auth import get_current_user

router = APIRouter()


@router.get("/search")
async def search_properties(
    destination: str = Query(..., title="Destination"),
    from_date: str = Query(..., title="From Date"),
    to_date: str = Query(..., title="To Date"),
):
    """Find properties in `destination` with no booking overlapping the date range."""
    query = {
        "location": {"$regex": destination, "$options": "i"},
        "$nor": [
            {
                "booking_history": {
                    "$elemMatch": {
                        "start_date": {"$lt": to_date},
                        "end_date": {"$gt": from_date},
                    }
                }
            },
            {"booking_history": {"$exists": False}},
        ],
    }
    projection = {
        "_id": 0,
        "property_id": 1,
        "title": 1,
        "price": 1,
        "location": 1,
        "rating": 1,
        "summary": 1,
    }

    properties = list(listing_collection.find(query, projection))
    push_to_redis(
        "Search '{}' {} to {} matched {} properties".format(
            destination, from_date, to_date, len(properties)
        )
    )
    return properties


@router.post("/reserve/{property_id}")
async def reserve_property(
    property_id: int,
    start_date: str = Body(...),
    end_date: str = Body(...),
    current_user: int = Depends(get_current_user),
):
    user_id = int(current_user)
    booking_entry = {
        "user_id": user_id,
        "start_date": start_date,
        "end_date": end_date,
    }

    updated_property = listing_collection.find_one_and_update(
        {"property_id": property_id},
        {"$push": {"booking_history": booking_entry}},
        return_document=pymongo.ReturnDocument.AFTER,
    )
    if updated_property is None:
        raise HTTPException(status_code=404, detail="Property not found")

    updated_user = user_collection.find_one_and_update(
        {"user_id": user_id},
        {"$set": {f"trips.{property_id}": []}},
        return_document=pymongo.ReturnDocument.AFTER,
    )
    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    updated_property["_id"] = str(updated_property["_id"])
    updated_user["_id"] = str(updated_user["_id"])

    push_to_redis("Reserved property {} for user {}".format(property_id, user_id))
    return {
        "message": "Reservation successful",
        "updated_property": updated_property,
        "updated_user": updated_user,
    }
