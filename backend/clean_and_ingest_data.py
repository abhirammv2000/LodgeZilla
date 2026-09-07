"""One-off loader: cleans the Airbnb CSV exports and seeds MongoDB.

Run from the `backend/` directory:  python clean_and_ingest_data.py
"""
import os
import random
import time

import emoji
import pandas as pd
import pymongo
from bs4 import BeautifulSoup

from app.db import listing_collection, mongo_client, user_collection
from app.util.utils import generate_password


def parse_clean_add_listings_data(src_dir):
    """
    CSV files in src_dir must have a predefined naming format which is listings-{city}.csv
    """
    for file in os.listdir(src_dir):
        if not file.lower().startswith('listings'):
            continue
        file_path = os.path.join(src_dir, file)
        df = pd.read_csv(file_path)
        df = df[df["id"].notna() & df["name"].notna()]
        df["description"].fillna("", inplace=True)
        df["price"].fillna(0, inplace=True)
        df["neighborhood_overview"].fillna("", inplace=True)
        df["neighbourhood_cleansed"].fillna("", inplace=True)

        property_id = df["id"]
        title = df["name"].str.replace("★[0-9.]+", "", regex=True).apply(lambda x: " ".join(" ".join(x.split("·")).split()))
        rating = df["name"].str.extract("★([0-9.]+)").fillna(0).squeeze().apply(lambda x: float(x))
        summary = df["description"].apply(lambda x: " ".join(x.split())) + " " + df["neighborhood_overview"].apply(lambda x: " ".join(x.split()))
        summary = summary.apply(lambda x: BeautifulSoup(x, "html.parser").text)
        price = df["price"].apply(lambda x: float(x.split("$")[1].replace(",", "")) if len(x) > 0 and "$" in x else float(x))
        location = os.path.splitext(file)[0].split("-")[1] + (", " + df["neighbourhood_cleansed"] if not df["neighbourhood_cleansed"].empty else "")
        booking_history = [[]] * len(df)
        clean_df = pd.DataFrame({"property_id": property_id, "title": title, "rating": rating, "summary": summary,
                                 "price": price, "location": location, "booking_history": booking_history})
        data_dict = clean_df.to_dict(orient="records")
        listing_collection.insert_many(data_dict)
    return 1


def parse_clean_add_user_data(src_dir):
    """
    CSV files in src_dir must have a predefined naming format which is reviews-{city}.csv
    """

    for file in os.listdir(src_dir):
        user_id_map = {}
        batch_process = {}
        records_= []
        if not file.lower().startswith('reviews'):
            continue
        file_path = os.path.join(src_dir, file)
        df = pd.read_csv(file_path)
        df = df[df["listing_id"].notna() & df["reviewer_id"].notna() ]
        df["comments"].fillna("", inplace=True)

        df_user_id = df["reviewer_id"]
        df_name = df["reviewer_name"]
        df_listing_id = df["listing_id"]
        df_comments = df["comments"]
        df_comments = df_comments.apply(lambda x: BeautifulSoup(x, "html.parser").text)
        for user_id_, name_, listing_id_, comments_ in zip(df_user_id, df_name, df_listing_id, df_comments):
            comments_ = emoji.demojize(comments_.strip())
            if user_id_ not in user_id_map:
                record_ = {"user_id": user_id_, "password": generate_password(), "name": name_, "trips": {str(listing_id_): [comments_]}}
                records_.append(record_)
                user_id_map[user_id_] = 0
            else:
                if user_id_ not in batch_process:
                    batch_process[user_id_] = {}
                trip_ = "trips.{}".format(listing_id_)

                if trip_ not in batch_process[user_id_]:
                    batch_process[user_id_][trip_] = [comments_]
                else:
                    batch_process[user_id_][trip_].append(comments_)

        user_collection.insert_many(records_)
        if len(batch_process) == 0:
            continue
        bulk_write_updates = []
        for user_id_, updates_ in batch_process.items():
            where_clause = {"user_id": user_id_}
            for k, v in updates_.items():
                update_operation = {"$push": {k: {"$each": v}}}
                bulk_write_updates.append(pymongo.UpdateOne(where_clause, update_operation))
        result = user_collection.bulk_write(bulk_write_updates)
    return 1

def add_random_user_type():
    # Find users without userType field
    users_without_user_type = user_collection.find({"userType": {"$exists": False}})

    # Iterate through each user and update with a random userType
    for user in users_without_user_type:
        random_user_type = random.choice(["host", "tourist"])
        user_collection.update_one({"_id": user["_id"]}, {"$set": {"userType": random_user_type}})

    print("User types randomly allocated for users without userType field.")
    return

def assign_hosts():
    host_user_ids = [user["user_id"] for user in user_collection.find({"userType": "host"})]
    if not host_user_ids:
        print("No hosts available.")
        return

    # Give every property a randomly chosen host.
    for property_doc in listing_collection.find():
        listing_collection.update_one(
            {"_id": property_doc["_id"]},
            {"$set": {"host": random.choice(host_user_ids)}},
        )

    print("Hosts assigned to properties successfully.")


if __name__ == "__main__":
    started = time.time()
    data_folder = "app/data"
    parse_clean_add_listings_data(data_folder)
    parse_clean_add_user_data(data_folder)
    add_random_user_type()
    assign_hosts()
    mongo_client.close()
    print("time: {:.1f}s".format(time.time() - started))

