import streamlit as st
from dotenv import load_dotenv
from openai import AzureOpenAI
import os
import json
from pymongo import MongoClient
import pandas as pd
import time

MONGO_CLIENT = MongoClient("mongo:27017")
DATABASE = MONGO_CLIENT["aiquiz"]
COLLECTION_IMAGE_SUBMISSION = DATABASE["image_submission"]
COLLECTION_GAMESTATE = DATABASE["game_state"]
COLLECTION_GROUPS = DATABASE["groups"]
COLLECTION_QUIZ = DATABASE["quiz"]
COLLECTION_QUIZ_SUBMISSION = DATABASE["quiz_submission"]
OPENAI_CLIENT = AzureOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    api_version="2024-07-01-preview",
    azure_endpoint="https://corra-test.openai.azure.com/",
)
MODEL_NAME = "gpt4o"
# refresh streamlit app every 2 second for image_submission_stage and quiz_round_stage
TIME_TO_REFRESH = 2

try:
    st.session_state["round"] = COLLECTION_GAMESTATE.find_one(
        {"round": {"$exists": True}}
    )["round"]
except:
    COLLECTION_GAMESTATE.insert_one({"round": 1})
    COLLECTION_GAMESTATE.insert_one({"state": "image_submission_stage"})
    st.session_state["round"] = 1

if "game_state" not in st.session_state:
    st.session_state["game_state"] = COLLECTION_GAMESTATE.find_one(
        {"state": {"$exists": True}}
    )["state"]
    st.session_state["generation"] = False
    st.session_state.disable_start_new_round = True

if "all_submissions_received" not in st.session_state:
    st.session_state.all_submissions_received = False


def update_gamestate(gamestate):
    # "image_submission_stage",
    # "quiz_round_stage",
    # "end_quiz_round_stage",
    if COLLECTION_GAMESTATE.find_one({"state": {"$exists": True}}):
        COLLECTION_GAMESTATE.update_one(
            {"state": {"$exists": True}}, {"$set": {"state": gamestate}}
        )
    else:
        COLLECTION_GAMESTATE.insert_one({"state": gamestate})

    st.session_state["game_state"] = gamestate

    if gamestate == "image_submission_stage":
        st.session_state["generation"] = False


def update_gameround(gameround):
    # game round represent the number of rounds that the game has been played
    if COLLECTION_GAMESTATE.find_one({"round": {"$exists": True}}):
        COLLECTION_GAMESTATE.update_one(
            {"round": {"$exists": True}}, {"$set": {"round": gameround}}
        )
    else:
        COLLECTION_GAMESTATE.insert_one({"round": gameround})

    st.session_state["round"] = gameround


def create_quiz(round, group, image, og_prompt, syn_prompt1, syn_prompt2, syn_prompt3):
    if COLLECTION_QUIZ.find_one({"round": round}):
        COLLECTION_QUIZ.update_one(
            {"round": round},
            {
                "$set": {
                    "group": group,
                    "url": image,
                    "og_prompt": og_prompt,
                    "syn_prompt1": syn_prompt1,
                    "syn_prompt2": syn_prompt2,
                    "syn_prompt3": syn_prompt3,
                }
            },
        )
    else:
        COLLECTION_QUIZ.insert_one(
            {
                "round": round,
                "group": group,
                "url": image,
                "og_prompt": og_prompt,
                "syn_prompt1": syn_prompt1,
                "syn_prompt2": syn_prompt2,
                "syn_prompt3": syn_prompt3,
            }
        )


def disable_generation_start_quiz():
    st.session_state["generation"] = True


def generate_3_prompts(image, original_prompt):
    try:
        response = OPENAI_CLIENT.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"""Given the original image generation prompt, '{original_prompt}', write me 3 additional prompts of similar style and tone that may be used to describe this image.
Return the prompts in a dictionary format as follows:
{{
    "prompt1":"generated prompt",
    "prompt2":"generated prompt",
    "prompt3":"generated prompt",
}}
Return only the final JSON dictionary. Do not return any other output descriptions or explanations, only the JSON dictionary.""",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image,
                            },
                        },
                    ],
                }
            ],
            max_tokens=300,
        )
        print(response)
        # print(response.choices[0].message.content)
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        # General exception handling with detailed info
        print(f"An error occurred: {type(e).__name__} - {e}")
        return None


def reset_everything():
    COLLECTION_IMAGE_SUBMISSION.delete_many({})
    COLLECTION_GAMESTATE.delete_many({})
    COLLECTION_GROUPS.delete_many({})
    COLLECTION_QUIZ.delete_many({})
    COLLECTION_QUIZ_SUBMISSION.delete_many({})
    update_gamestate("image_submission_stage")
    update_gameround(1)
    st.session_state.all_submissions_received = False


def check_submissions(percentage):
    while True:
        if percentage == 1.0:
            st.session_state.all_submissions_received = True
            st.rerun()
            break
        else:
            time.sleep(TIME_TO_REFRESH)  # sleep for 3 seconds
            current_time = time.strftime("%H:%M:%S")
            st.write(f"Refreshed on {current_time}")
            st.rerun()


st.title("AI Quiz Admin Panel")

st.subheader("Game State")
st.success(
    f"Round {st.session_state['round']} Game State: {st.session_state['game_state']}"
)

st.button(
    "Image Submission Stage",
    on_click=update_gamestate,
    kwargs={"gamestate": "image_submission_stage"},
    use_container_width=True,
)


st.divider()

st.subheader("All Submissions")

all_submissions = list(
    COLLECTION_IMAGE_SUBMISSION.find({"round": st.session_state.round})
)

all_groups = [item["group"] for item in list(COLLECTION_GROUPS.find())]
image_submitted_groups = [submission["group"] for submission in all_submissions]
image_submission_status = {}
for group in all_groups:
    if group in image_submitted_groups:
        image_submission_status[group] = True
    else:
        image_submission_status[group] = False
if len(all_groups) > 0:
    image_submission_percentage = sum(image_submission_status.values()) / len(
        all_groups
    )
else:
    image_submission_percentage = 0.0
st.write(
    f"{sum(image_submission_status.values())} out of {len(all_groups)} groups submitted. ({image_submission_percentage*100:.2f}%)"
)
with st.expander("See Submission Status"):
    st.write(image_submission_status)

col1, col2, col3 = st.columns(3)

for id, submission in enumerate(all_submissions):
    if (id + 1) % 3 == 1:
        col1.write(f'Group {id + 1}: {submission["group"]}')
        col1.image(submission["url"])
        col1.caption(submission["prompt"])
    elif (id + 1) % 3 == 2:
        col2.write(f'Group {id + 1}: {submission["group"]}')
        col2.image(submission["url"])
        col2.caption(submission["prompt"])
    elif (id + 1) % 3 == 0:
        col3.write(f'Group {id + 1}: {submission["group"]}')
        col3.image(submission["url"])
        col3.caption(submission["prompt"])

selected_group = st.radio(
    "Select the group image to submit for quiz", range(1, len(all_submissions) + 1)
)

if st.button(
    "Generate 3 more prompts and Start Quiz Stage",
    on_click=disable_generation_start_quiz,
    disabled=st.session_state["generation"],
    use_container_width=True,
):
    if selected_group:
        # Generate 3 more synthetic prompts
        generated_prompts = generate_3_prompts(
            all_submissions[selected_group - 1]["url"],
            all_submissions[selected_group - 1]["prompt"],
        )

        # push selected image, og prompts and 3 synthetic prompts to db
        create_quiz(
            st.session_state["round"],
            all_submissions[selected_group - 1]["group"],
            all_submissions[selected_group - 1]["url"],
            all_submissions[selected_group - 1]["prompt"],
            generated_prompts["prompt1"],
            generated_prompts["prompt2"],
            generated_prompts["prompt3"],
        )

        # change game state to quiz stage
        update_gamestate(gamestate="quiz_round_stage")
        st.session_state.all_submissions_received = False
    else:
        st.warning("Please wait for at least a group to submit their image.")

st.divider()

st.subheader("SCORE")

df = list(COLLECTION_QUIZ_SUBMISSION.find())
df_current_round = [
    current for current in df if current["round"] == st.session_state.round
]
quiz_submitted_groups = [submission["group"] for submission in df_current_round]
quiz_submission_status = {}
for group in all_groups:
    if group in quiz_submitted_groups:
        quiz_submission_status[group] = True
    else:
        quiz_submission_status[group] = False
if len(all_groups) > 0:
    quiz_submission_percentage = sum(quiz_submission_status.values()) / len(all_groups)
else:
    quiz_submission_percentage = 0.0
st.write(
    f"{sum(quiz_submission_status.values())} out of {len(all_groups)} groups submitted. ({quiz_submission_percentage*100:.2f}%)"
)
with st.expander("See Quiz Submission Status"):
    st.write(quiz_submission_status)

if df:
    st.bar_chart(pd.DataFrame(df).groupby(["group"]).sum("score")[["score"]])

if st.button(
    "End Quiz Stage",
    on_click=update_gamestate,
    kwargs={"gamestate": "end_quiz_round_stage"},
    use_container_width=True,
):
    st.session_state.disable_start_new_round = False

if st.button(
    "Start New Round",
    on_click=update_gamestate,
    kwargs={"gamestate": "image_submission_stage"},
    use_container_width=True,
    disabled=st.session_state.disable_start_new_round,
):
    update_gameround(st.session_state.round + 1)
    st.session_state.all_submissions_received = False
    st.rerun()

if st.button(
    "RESET EVERYTHING!",
    use_container_width=True,
    type="primary",
):
    reset_everything()
    st.rerun()

st.session_state

# constantly refresh every second if all_submissions not received
if (
    st.session_state.game_state == "image_submission_stage"
    and st.session_state.all_submissions_received == False
):
    check_submissions(image_submission_percentage)
if (
    st.session_state.game_state == "quiz_round_stage"
    and st.session_state.all_submissions_received == False
):
    check_submissions(quiz_submission_percentage)
