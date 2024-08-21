import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
import os
import pandas as pd
from pymongo import MongoClient
import random
import time

load_dotenv()
MONGO_CLIENT = MongoClient("mongo:27017")
DATABASE = MONGO_CLIENT["aiquiz"]
COLLECTION_IMAGE_SUBMISSION = DATABASE["image_submission"]
COLLECTION_GAMESTATE = DATABASE["game_state"]
COLLECTION_QUIZ = DATABASE["quiz"]
COLLECTION_QUIZ_SUBMISSION = DATABASE["quiz_submission"]
OPENAI_CLIENT = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def click_submit(button):
    if button == "gamemaster":
        st.session_state.submitted = True
        st.session_state.disable_generate = True
    elif button == "submit_quiz":
        st.session_state.disable_submit_quiz = True


def update_or_insert_image(round, group, url, prompt):
    """update document if group is in collection, otherwise, insert new document"""
    if COLLECTION_IMAGE_SUBMISSION.find_one({"round": round, "group": group}):
        COLLECTION_IMAGE_SUBMISSION.update_one(
            {"round": round, "group": group}, {"$set": {"url": url, "prompt": prompt}}
        )
    else:
        COLLECTION_IMAGE_SUBMISSION.insert_one(
            {"round": round, "group": group, "url": url, "prompt": prompt}
        )


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
            time.sleep(3)  # sleep for 3 seconds


def reset_round():
    st.session_state.url = None
    st.session_state.disable_generate = False
    st.session_state.submitted = False
    st.session_state.game_state = COLLECTION_GAMESTATE.find_one(
        {"state": {"$exists": True}}
    )["state"]
    st.session_state.disable_submit_quiz = False
    st.session_state.round = COLLECTION_GAMESTATE.find_one(
        {"round": {"$exists": True}}
    )["round"]


try:
    st.session_state.round = COLLECTION_GAMESTATE.find_one(
        {"round": {"$exists": True}}
    )["round"]
    st.session_state.game_state = COLLECTION_GAMESTATE.find_one(
        {"state": {"$exists": True}}
    )["state"]
except:
    COLLECTION_GAMESTATE.insert_one({"round": 1})
    COLLECTION_GAMESTATE.insert_one({"state": "image_submission_stage"})
    st.session_state.round = 1
    st.session_state.game_state = "image_submission_stage"

if "url" not in st.session_state:
    st.session_state.url = None
    st.session_state.disable_generate = False
    st.session_state.submitted = False
    st.session_state.disable_submit_quiz = False

if "group" not in st.session_state:
    st.session_state.group = None

st.title("AI Quiz")
if st.session_state.group == None:
    groupname = st.text_input("Group Name:")
    if groupname:
        st.session_state.group = groupname
        st.rerun()
else:
    st.header(f"{st.session_state.group}: Round {st.session_state.round}")

    if st.session_state.game_state == "image_submission_stage":
        # User prompt input
        with st.form("my_form"):
            user_prompt = st.text_input("Enter your prompt:", key="prompt")
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
                        st.session_state.url = response.data[0].url
                    except:
                        st.error("Error generating image. Please try again.")

        if st.session_state.url:
            st.image(st.session_state.url)
            st.button(
                "Submit to Game Master",
                on_click=click_submit,
                args=("gamemaster",),
                disabled=st.session_state.disable_generate,
            )

        if st.session_state.submitted:
            update_or_insert_image(
                st.session_state.round,
                st.session_state.group,
                st.session_state.url,
                user_prompt,
            )

            st.success("Image submitted!")

            check_game_state()

    if st.session_state.game_state == "quiz_round_stage":

        st.session_state.round = COLLECTION_GAMESTATE.find_one(
            {"round": {"$exists": True}}
        )["round"]
        st.session_state.quiz = COLLECTION_QUIZ.find_one(
            {"round": st.session_state.round}
        )
        quiz_prompts = [
            st.session_state.quiz["og_prompt"],
            st.session_state.quiz["syn_prompt1"],
            st.session_state.quiz["syn_prompt2"],
            st.session_state.quiz["syn_prompt3"],
        ]
        random.Random(1).shuffle(quiz_prompts)
        st.session_state.randomised_quiz_prompts = quiz_prompts

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

    if st.session_state.game_state == "end_quiz_round_stage":

        st.subheader("Leaderboard")
        df = list(COLLECTION_QUIZ_SUBMISSION.find())
        st.bar_chart(pd.DataFrame(df).groupby(["group"]).sum("score")[["score"]])

        reset_round()
        check_game_state()


# TODO: count score base on time
# TODO: add disclaimer: no offensive words
# TODO: for Admin panel I need to be able to check who submitted answers
# TODO: Set min amount of word so that the prompt is more fun
# TODO: Fix bug of 3rd round showing 2nd round image
# TODO: change to 2xlarge
