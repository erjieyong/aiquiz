import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
import os
from pymongo import MongoClient

import asyncio

load_dotenv()
MONGO_CLIENT = MongoClient("mongodb://localhost:27017/")
OPENAI_CLIENT = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


st.title("AI Quiz Image Generator")

if "url" not in st.session_state:
    st.session_state["url"] = None
    st.session_state["disable_generate"] = False
    st.session_state["submitted"] = False
    st.session_state["game_state"] = "0"


def disable():
    st.session_state.disable_generate = True


def click_submit():
    st.session_state.submitted = True
    disable()


def update_or_insert_doc(collection, group, url):
    """update document if group is in collection, otherwise, insert new document"""
    if collection.find_one({"group": group}):
        collection.update_one({"group": group}, {"$set": {"url": url}})
    else:
        collection.insert_one({"group": group, "url": url})


def check_document():
    db = MONGO_CLIENT["aiquiz"]
    collection = db["game_state"]
    doc = collection.find_one()
    print("game state: ", doc["state"])
    st.session_state["game_state"] = doc["state"]


check_document()

if st.session_state["game_state"] == "0":
    # User prompt input
    with st.form("my_form"):
        group_name = st.text_input("Group Name:")
        user_prompt = st.text_input("Enter your prompt:")
        generate = st.form_submit_button(
            "Generate Image", disabled=st.session_state.disable_generate
        )

    # Generate button
    if generate:
        if not user_prompt:
            st.warning("Please enter a prompt.")
        else:
            with st.spinner(text="Generating image..."):
                response = OPENAI_CLIENT.images.generate(
                    model="dall-e-2",
                    prompt=user_prompt,
                    size="256x256",
                    quality="standard",
                    n=1,
                )
                try:
                    st.session_state["url"] = response.data[0].url
                except:
                    st.error("Error generating image. Please try again.")

    if st.session_state["url"]:
        st.image(st.session_state["url"])
        st.button("Submit to Game Master", on_click=click_submit)

    if st.session_state.submitted:
        # List all databases
        # databases = MONGO_CLIENT.list_database_names()
        db = MONGO_CLIENT["aiquiz"]
        collection = db["image_submission"]

        update_or_insert_doc(collection, group_name, st.session_state["url"])

        st.success("Image submitted!")

    # TODO: continuosly check for status of a document in mongodb collection to see if the game has started. Explore just checking at the end of each action
    # TODO: create admin panel that monitors when how many team has submitted the pic or participated

    document_value = st.empty()

    # # Async function to check document value
    # async def check_document():
    #     db = MONGO_CLIENT["aiquiz"]
    #     collection = db["game_state"]
    #     doc = collection.find_one()
    #     return doc["state"]

    # # Define an async function to periodically check for updates
    # async def monitor_changes():
    #     current_value = await check_document()
    #     document_value.write(f"Current Value: {current_value}")

    #     while True:
    #         await asyncio.sleep(5)  # Delay to avoid overwhelming the database
    #         new_value = await check_document()
    #         if new_value != current_value:
    #             current_value = new_value
    #             document_value.write(f"Updated Value: {current_value}")

    # # Run the async function in the background
    # asyncio.run(monitor_changes())
elif st.session_state["game_state"] == "1":
    st.write("quiz page")
