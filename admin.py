import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
import os
import json
from pymongo import MongoClient
import pandas as pd

load_dotenv()
MONGO_CLIENT = MongoClient("mongodb://localhost:27017/")
DATABASE = MONGO_CLIENT["aiquiz"]
COLLECTION_IMAGE_SUBMISSION = DATABASE["image_submission"]
COLLECTION_GAMESTATE = DATABASE["game_state"]
COLLECTION_QUIZ = DATABASE["quiz"]
COLLECTION_QUIZ_SUBMISSION = DATABASE["quiz_submission"]
OPENAI_CLIENT = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.session_state["round"] = COLLECTION_GAMESTATE.find_one({"round": {"$exists": True}})[
    "round"
]

if "game_state" not in st.session_state:
    st.session_state["game_state"] = COLLECTION_GAMESTATE.find_one()["state"]
    st.session_state["generation"] = False


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
    print(group, image)
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
    response = OPENAI_CLIENT.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""Given this image, write me 3 potential prompts in {len(original_prompt.split(" "))} words each that may be used to generate this image. Do not repeat the original prompt `{original_prompt}`. 
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
    print(response.choices[0].message.content)
    return json.loads(response.choices[0].message.content)


def reset_everything():
    COLLECTION_IMAGE_SUBMISSION.delete_many({})
    COLLECTION_GAMESTATE.delete_many({})
    COLLECTION_QUIZ.delete_many({})
    COLLECTION_QUIZ_SUBMISSION.delete_many({})
    update_gamestate("image_submission_stage")
    update_gameround(1)


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
col1, col2, col3 = st.columns(3)

all_submissions = list(COLLECTION_IMAGE_SUBMISSION.find())

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
    else:
        st.warning("Please wait for at least a group to submit their image.")

st.divider()

st.subheader("SCORE")
df = list(COLLECTION_QUIZ_SUBMISSION.find())
if df:
    st.bar_chart(pd.DataFrame(df).groupby(["group"]).sum("score")[["score"]])

st.button(
    "End Quiz Stage",
    on_click=update_gamestate,
    kwargs={"gamestate": "end_quiz_round_stage"},
    use_container_width=True,
)

if st.button(
    "Start New Round",
    on_click=update_gamestate,
    kwargs={"gamestate": "image_submission_stage"},
    use_container_width=True,
):
    update_gameround(st.session_state.round + 1)

if st.button(
    "RESET EVERYTHING!",
    use_container_width=True,
    type="primary",
):
    reset_everything()
    st.rerun()

st.session_state

# TODO: real time update of how many teams and which team has submitted.
# TODO: current score may need to take into account the timing
