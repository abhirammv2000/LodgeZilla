from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from bson.json_util import dumps

from ..db import listing_collection, push_to_redis
from ..model.listing import Property
from .auth import get_current_user

router = APIRouter()


def _serialize(listings):
    """Return listings as a normal JSON array body.

    bson.json_util.dumps (not plain json.dumps) is what actually matters here
    - it knows how to encode BSON types a raw pymongo document can still carry
    (datetimes, Decimal128, etc.) even though _id is stringified above.
    Passing its output through JSONResponse used to double-encode it: JSONResponse
    itself calls json.dumps on whatever `content` is, so a Python str got
    wrapped in JSON-string quoting on top of the JSON dumps() had already
    produced, and the frontend had to JSON.parse the response body a second
    time to undo it. Response with an explicit media_type sends dumps()'s
    bytes as-is, so the wire format is just the array - one parse, not two.
    """
    for listing in listings:
        listing["_id"] = str(listing["_id"])
    return Response(content=dumps(listings), media_type="application/json")


@router.get("/list")
async def get_listings():
    listings = list(listing_collection.find())
    push_to_redis("Listed {} properties".format(len(listings)))
    return _serialize(listings)


@router.get("/list/{user_id}")
async def get_listings_for_host(user_id: int):
    listings = list(listing_collection.find({"host": user_id}))
    push_to_redis("Listed {} properties for host {}".format(len(listings), user_id))
    return _serialize(listings)


@router.post("/add", response_model=Property)
async def create_item(listing: Property, current_user: str = Depends(get_current_user)):
    result = listing_collection.insert_one(listing.dict())
    push_to_redis("Inserted result id {}".format(result.inserted_id))
    return {**listing.dict(), "id": str(result.inserted_id)}


def _assert_owner(existing_data: dict, current_user: str) -> None:
    """Only the host who owns a listing may change or remove it.

    current_user is the JWT subject, a string (see auth.py's create_jwt_token,
    which stringifies sub); host is stored as an int, so the comparison
    normalizes both to str rather than assuming one side's type.
    """
    if str(existing_data.get("host")) != str(current_user):
        raise HTTPException(status_code=403, detail="Not the owner of this property")


@router.put("/update/{property_id}", response_model=Property)
async def update_property(
    property_id: int,
    updated_data: Property,
    current_user: str = Depends(get_current_user),
):
    existing_data = listing_collection.find_one({"property_id": property_id})
    if existing_data is None:
        raise HTTPException(status_code=404, detail="Property not found")
    _assert_owner(existing_data, current_user)

    merged_data = {**existing_data, **updated_data.dict(exclude_unset=True)}
    listing_collection.update_one({"property_id": property_id}, {"$set": merged_data})
    push_to_redis("Updated property id {}".format(property_id))
    return merged_data


@router.delete("/delete/{property_id}")
async def delete_property(
    property_id: int, current_user: str = Depends(get_current_user)
):
    existing_data = listing_collection.find_one({"property_id": property_id})
    if existing_data is None:
        raise HTTPException(status_code=404, detail="Property not found")
    _assert_owner(existing_data, current_user)

    listing_collection.delete_one({"property_id": property_id})
    push_to_redis("Deleted property id {}".format(property_id))
    return {"status": "success", "message": "Property deleted successfully"}
