import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
import os
import json
from pymongo import MongoClient

load_dotenv()
MONGO_CLIENT = MongoClient("mongodb://localhost:27017/")
DATABASE = MONGO_CLIENT["aiquiz"]
COLLECTION_IMAGE_SUBMISSION = DATABASE["image_submission"]
COLLECTION_GAMESTATE = DATABASE["game_state"]
COLLECTION_QUIZ = DATABASE["quiz"]
OPENAI_CLIENT = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

if "game_state" not in st.session_state:
    st.session_state["game_state"] = COLLECTION_GAMESTATE.find_one()["state"]
    st.session_state["generation"] = False
    st.session_state["round"] = 1


def update_gamestate(collection, gamestate):
    if collection.find_one({"state": {"$regex": "\d"}}):
        collection.update_one(
            {"state": {"$regex": "\d"}}, {"$set": {"state": gamestate}}
        )
    else:
        collection.insert_one({"state": gamestate})

    st.session_state["game_state"] = gamestate

    if gamestate == "0":
        st.session_state["generation"] = False


def update_quiz(round, group, image, og_prompt, syn_prompt1, syn_prompt2, syn_prompt3):
    COLLECTION_QUIZ.insert_one(
        {
            "round": round,
            "group": group,
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


st.title("AI Quiz Admin Panel")

st.subheader("Set Game State")
# 0: image submission
# 1: quiz time
# 2: end quiz and show result
gamestate_dic = {
    "0": "Image Submission Stage",
    "1": "Quiz Stage",
    "2": "End Quiz Stage",
}


current_gamestate = st.empty()

col1, col2, col3 = st.columns(3)
col1.button(
    "Image Submission Stage",
    on_click=update_gamestate,
    kwargs={"collection": COLLECTION_GAMESTATE, "gamestate": "0"},
    use_container_width=True,
)
# col2.button(
#     "Quiz Stage",
#     on_click=update_gamestate,
#     kwargs={"collection": COLLECTION_GAMESTATE, "gamestate": "1"},
#     use_container_width=True,
# )
col3.button(
    "End Quiz Stage",
    on_click=update_gamestate,
    kwargs={"collection": COLLECTION_GAMESTATE, "gamestate": "2"},
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

if st.session_state["game_state"] == "0":
    if st.button(
        "Generate 3 more prompts and start quiz",
        on_click=disable_generation_start_quiz,
        disabled=st.session_state["generation"],
    ):
        # Generate 3 more synthetic prompts
        generated_prompts = generate_3_prompts(
            all_submissions[selected_group - 1]["url"],
            all_submissions[selected_group - 1]["prompt"],
        )

        # push selected image, og prompts and 3 synthetic prompts to db
        update_quiz(
            st.session_state["round"],
            all_submissions[selected_group - 1]["group"],
            all_submissions[selected_group - 1]["url"],
            all_submissions[selected_group - 1]["prompt"],
            generated_prompts["prompt1"],
            generated_prompts["prompt2"],
            generated_prompts["prompt3"],
        )

        # change game state to quiz stage
        update_gamestate(collection=COLLECTION_GAMESTATE, gamestate="1")

current_gamestate.success(
    f"Round {st.session_state['round']} Game State: {gamestate_dic[st.session_state['game_state']]}"
)
st.session_state

# TODO: tally results for all group
# TODO: end quiz and increase round by 1
