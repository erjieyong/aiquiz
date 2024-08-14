import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
import os
from pymongo import MongoClient
import random
import time

import asyncio

load_dotenv()
MONGO_CLIENT = MongoClient("mongodb://localhost:27017/")
DATABASE = MONGO_CLIENT["aiquiz"]
COLLECTION_IMAGE_SUBMISSION = DATABASE["image_submission"]
COLLECTION_GAMESTATE = DATABASE["game_state"]
COLLECTION_QUIZ = DATABASE["quiz"]
COLLECTION_QUIZ_SUBMISSION = DATABASE["quiz_submission"]
OPENAI_CLIENT = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


if "url" not in st.session_state:
    st.session_state["url"] = None
    st.session_state["disable_generate"] = False
    st.session_state["submitted"] = False
    st.session_state["game_state"] = COLLECTION_GAMESTATE.find_one(
        {"state": {"$exists": True}}
    )["state"]
    st.session_state.round = COLLECTION_GAMESTATE.find_one(
        {"round": {"$exists": True}}
    )["round"]
    st.session_state.disable_submit_quiz = False
    st.session_state.group = ""

st.title("AI Quiz Image Generator")
st.header(f"Round {st.session_state.round}")


def click_submit(button):
    if button == "gamemaster":
        st.session_state.submitted = True
        st.session_state.disable_generate = True
    elif button == "submit_quiz":
        st.session_state.disable_submit_quiz = True


def update_or_insert_doc(collection, group, url, prompt):
    """update document if group is in collection, otherwise, insert new document"""
    if collection.find_one({"group": group}):
        collection.update_one(
            {"group": group}, {"$set": {"url": url, "prompt": prompt}}
        )
    else:
        collection.insert_one({"group": group, "url": url, "prompt": prompt})


def submit_score(round, group, score):
    if COLLECTION_QUIZ_SUBMISSION.find_one({"round": round, "group": group}):
        st.warning("You can't submit twice for the same round!")
    else:
        COLLECTION_QUIZ_SUBMISSION.insert_one(
            {"round": round, "group": group, "score": score}
        )


def check_game_state():
    while True:
        new_state = COLLECTION_GAMESTATE.find_one({"state": {"$exists": True}})["state"]
        if new_state != st.session_state.game_state:
            st.session_state.game_state = new_state
            st.rerun()
            break
        else:
            time.sleep(5)  # sleep for 5 seconds


def reset_round():
    st.session_state["url"] = None
    st.session_state["disable_generate"] = False
    st.session_state["submitted"] = False
    st.session_state["game_state"] = COLLECTION_GAMESTATE.find_one(
        {"state": {"$exists": True}}
    )["state"]
    st.session_state.disable_submit_quiz = False
    st.session_state.round = COLLECTION_GAMESTATE.find_one(
        {"round": {"$exists": True}}
    )["round"]


if st.session_state["game_state"] == "0":
    # User prompt input
    with st.form("my_form"):
        group_name = st.text_input("Group Name:")
        st.session_state.group = group_name
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
        st.button(
            "Submit to Game Master",
            on_click=click_submit,
            args=("gamemaster",),
            disabled=st.session_state.disable_generate,
        )

    if st.session_state.submitted:
        update_or_insert_doc(
            COLLECTION_IMAGE_SUBMISSION,
            group_name,
            st.session_state["url"],
            user_prompt,
        )

        st.success("Image submitted!")

        check_game_state()


if st.session_state["game_state"] == "1":

    st.session_state.round = COLLECTION_GAMESTATE.find_one(
        {"round": {"$exists": True}}
    )["round"]
    st.session_state.quiz = COLLECTION_QUIZ.find_one({"round": st.session_state.round})
    quiz_prompts = [
        st.session_state.quiz["og_prompt"],
        st.session_state.quiz["syn_prompt1"],
        st.session_state.quiz["syn_prompt2"],
        st.session_state.quiz["syn_prompt3"],
    ]
    random.shuffle(quiz_prompts)
    if "randomised_quiz_prompts" not in st.session_state:
        st.session_state.randomised_quiz_prompts = quiz_prompts

    # st.write(f"Group name: {st.session_state.group}")
    if st.session_state.group == "":
        group_name = st.text_input("Group Name:")
        st.session_state.group = group_name

    # st.subheader(f"{st.session_state.group} Round {st.session_state.round}")

    col1, col2, col3 = st.columns(3)
    col2.image(st.session_state.quiz["url"])

    selected_answer = st.radio(
        "Which of the following prompt is the original prompt that was used to generate the image?",
        st.session_state.randomised_quiz_prompts,
        disabled=st.session_state.disable_submit_quiz,
    )

    if st.button(
        "Submit answer!",
        on_click=click_submit,
        args=("submit_quiz",),
        disabled=st.session_state.disable_submit_quiz,
    ):
        if selected_answer == st.session_state.quiz["og_prompt"]:
            st.success("Congratulations! You are correct!")
            submit_score(st.session_state.round, st.session_state.group, 1)
        else:
            st.error(
                f"Wrong! '**{st.session_state.quiz['og_prompt']}**' is the correct answer."
            )
            submit_score(st.session_state.round, st.session_state.group, 0)

        check_game_state()

if st.session_state["game_state"] == "2":
    reset_round()

    st.subheader("Leaderboard")
    for document in COLLECTION_QUIZ_SUBMISSION.find():
        st.write(document)

    check_game_state()

st.session_state

# TODO: ensure that the group name remains across 2 gamestate and user don't need to refresh
# TODO: after submit answer, we need to reset a few things such as the buttom submission
# TODO: at end quiz stage, display the current score

# # Async function to check document value
# async def check_document():
#     doc = COLLECTION_GAMESTATE.find_one({"state": {"$exists": True}})
#     return doc["state"]


# # Define an async function to periodically check for updates
# async def monitor_changes():
#     current_value = await check_document()
#     st.session_state["game_state"] = current_value
#     # document_value.write(f"Current Value: {current_value}")

#     while True:
#         await asyncio.sleep(5)  # Delay to avoid overwhelming the database
#         new_value = await check_document()
#         if new_value != current_value:
#             current_value = new_value
#             st.session_state["game_state"] = current_value
#             print(current_value)

#     # document_value.write(f"Updated Value: {current_value}")


# # Run the async function in the background
# asyncio.run(monitor_changes())
