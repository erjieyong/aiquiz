import streamlit as st
from openai import AzureOpenAI

def create_image(prompt):
    OPENAI_CLIENT = AzureOpenAI(
        api_key="1a449e0d38bb4cd8b7ecf968b6ecee13",
        api_version="2024-07-01-preview",
        azure_endpoint="https://corra-test.openai.azure.com/",
    )
    MODEL_NAME = "dalle3"

    response = OPENAI_CLIENT.images.generate(
        model=MODEL_NAME,
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )

    return response.data[0].url

st.title("Image Generator")
with st.form(key="image_submission_form"):
    st.write(
        "Please do not use any offensive words. Min 5 words required to generate image."
    )
    user_prompt = st.text_area(
        "Enter your prompt:",
        key="prompt",
    )
    generate = st.form_submit_button(
        "Generate Image",
    )

if generate:
    image_url = create_image(user_prompt)
    st.image(image_url)
