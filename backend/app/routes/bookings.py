import datetime
import re

from fastapi import APIRouter, Body, Depends, HTTPException, Query
import pymongo

from ..db import listing_collection, push_to_redis, user_collection
from .auth import get_current_user

router = APIRouter()

# Dates are compared as strings, which is only correct for this shape (zero padded, year first).
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _check_dates(start_date: str, end_date: str) -> None:
    """Reject a date range that string comparison would silently get wrong."""
    for name, value in (("start_date", start_date), ("end_date", end_date)):
        try:
            if not _ISO_DATE.match(value):
                raise ValueError
            datetime.date.fromisoformat(value)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"{name} must be a date like 2024-06-30")
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="end_date must not be before start_date")


@router.get("/search")
def search_properties(
    destination: str = Query(..., title="Destination"),
    from_date: str = Query(..., title="From Date"),
    to_date: str = Query(..., title="To Date"),
):
    """Find properties in `destination` with no booking overlapping the date range."""
    # re.escape so a destination containing regex metacharacters (a stray
    # ".*", say) searches for that literal text instead of being interpreted
    # as a pattern; an unescaped, unanchored $regex is also a full
    # collection-scan DoS vector since it can't use an index.
    query = {
        "location": {"$regex": re.escape(destination), "$options": "i"},
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
def reserve_property(
    property_id: int,
    start_date: str = Body(...),
    end_date: str = Body(...),
    current_user: int = Depends(get_current_user),
):
    """Book a property for a date range, or answer 409 if any part of it is taken.

    This is a plain `def` so FastAPI runs it on a worker thread. The database calls block, and in
    an `async def` they would stop the whole event loop for their duration.

    Two requests for overlapping dates can arrive at the same moment, on this process or on
    another replica, so the check and the write have to be one operation. They are: the update
    only matches a listing that has no booking overlapping the range, and MongoDB applies a
    single-document update atomically. Checking first and writing second would let both
    requests pass the check.
    """
    _check_dates(start_date, end_date)
    user_id = int(current_user)

    # Look the user up before touching the listing, so an unknown user cannot leave a booking
    # behind.
    if user_collection.find_one({"user_id": user_id}, {"_id": 1}) is None:
        raise HTTPException(status_code=404, detail="User not found")

    # A listing added through the API has booking_history null, and $push onto null is an error
    # in MongoDB. This turns null or a missing field into an empty list and leaves a list alone.
    listing_collection.update_one(
        {"property_id": property_id, "booking_history": None},
        {"$set": {"booking_history": []}},
    )

    booking_entry = {
        "user_id": user_id,
        "start_date": start_date,
        "end_date": end_date,
    }
    # the same overlap test that search uses
    overlapping = {"start_date": {"$lt": end_date}, "end_date": {"$gt": start_date}}
    updated_property = listing_collection.find_one_and_update(
        {"property_id": property_id, "booking_history": {"$not": {"$elemMatch": overlapping}}},
        {"$push": {"booking_history": booking_entry}},
        return_document=pymongo.ReturnDocument.AFTER,
    )
    if updated_property is None:
        if listing_collection.count_documents({"property_id": property_id}, limit=1) == 0:
            raise HTTPException(status_code=404, detail="Property not found")
        raise HTTPException(status_code=409, detail="Property is already booked for those dates")

    updated_user = user_collection.find_one_and_update(
        {"user_id": user_id},
        {"$set": {f"trips.{property_id}": []}},
        return_document=pymongo.ReturnDocument.AFTER,
    )
    if updated_user is None:  # deleted in the moments since the check above
        raise HTTPException(status_code=404, detail="User not found")

    updated_property["_id"] = str(updated_property["_id"])
    updated_user["_id"] = str(updated_user["_id"])

    push_to_redis("Reserved property {} for user {}".format(property_id, user_id))
    return {
        "message": "Reservation successful",
        "updated_property": updated_property,
        "updated_user": updated_user,
    }
