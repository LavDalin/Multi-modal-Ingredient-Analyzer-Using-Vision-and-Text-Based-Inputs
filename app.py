import streamlit as st
import os
from phi.agent import Agent
from phi.model.google import Gemini
from phi.tools.tavily import TavilyTools
from tempfile import NamedTemporaryFile
from PIL import Image
from io import BytesIO
from constants import SYSTEM_PROMPT, INSTRUCTIONS

# Streamlit page config
st.set_page_config(page_title="Product Ingredient Agent", layout="wide", initial_sidebar_state="collapsed")

# Set API keys from secrets
os.environ['TAVILY_API_KEY'] = st.secrets['TAVILY_KEY']
os.environ['GOOGLE_API_KEY'] = st.secrets['GEMINI_KEY']

# Initialize the agent
@st.cache_resource
def get_agent():
    return Agent(
        model=Gemini(id="gemini-2.0-flash"),
        system_prompt=SYSTEM_PROMPT,
        instructions=INSTRUCTIONS,
        tools=[TavilyTools(api_key=os.getenv("TAVILY_API_KEY"))],
        markdown=True,
    )

# Resize image for display
MAX_IMAGE_WIDTH = 300

def resize_image_for_display(image_file):
    if isinstance(image_file, str):
        img = Image.open(image_file)
    else:
        img = Image.open(image_file)
        image_file.seek(0)

    aspect_ratio = img.height / img.width
    new_height = int(MAX_IMAGE_WIDTH * aspect_ratio)
    img = img.resize((MAX_IMAGE_WIDTH, new_height), Image.Resampling.LANCZOS)
    
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# Save uploaded image file
def save_uploaded_file(uploaded_file):
    with NamedTemporaryFile(dir='.', suffix='.jpg', delete=False) as f:
        f.write(uploaded_file.getbuffer())
        return f.name

# Analyze image (extracting ingredients)
def analyze_image(image_path):
    agent = get_agent()
    with st.spinner('Analyzing image...'):
        response = agent.run(
            "Analyze the given image",
            images=[image_path],
        )
        st.session_state.ingredients = response.content
        st.markdown(response.content)

# Main app logic
def main():
    st.title("Product Ingredient Analyzer")

    if 'ingredients' not in st.session_state:
        st.session_state.ingredients = None

    # Upload Image Section
    st.subheader("Upload Photo")
    uploaded_file = st.file_uploader(
        "Upload image",
        type=["jpg", "jpeg", "png"],
        help="Upload a clear image of the product's ingredient list"
    )
    if uploaded_file:
        resized_image = resize_image_for_display(uploaded_file)
        st.image(resized_image, caption="Photo", use_container_width=False, width=MAX_IMAGE_WIDTH)
        if st.button("Analyze Photo", key="analyze_upload"):
            temp_path = save_uploaded_file(uploaded_file)
            analyze_image(temp_path)
            os.unlink(temp_path)

    # Capture Image Section
    
    st.subheader("Take Photo")

    if 'show_camera' not in st.session_state:
        st.session_state.show_camera = False

    if not st.session_state.show_camera:
        if st.button("Click Photo"):
            st.session_state.show_camera = True
    else:
        camera_photo = st.camera_input("Take a picture of the product")
        if camera_photo:
            resized_image = resize_image_for_display(camera_photo)
            st.image(resized_image, caption="Photo", use_container_width=False, width=MAX_IMAGE_WIDTH)
            if st.button("Analyze Photo", key="analyze_camera"):
                temp_path = save_uploaded_file(camera_photo)
                analyze_image(temp_path)
                os.unlink(temp_path)
            # Optionally reset to hide the camera again
            st.session_state.show_camera = False


    # Ask users for more questions
    st.subheader("Ask More Questions")
    user_question = st.text_input("Ask a question about the product or ingredients:")

    if user_question:
        agent = get_agent()
        if st.session_state.ingredients:
            question = f"""
            You are a product ingredient expert. Here is the extracted ingredient list:

            {st.session_state.ingredients}

            Now answer this question specifically based on the ingredients above:
            {user_question}
            """
        else:
            question = user_question

        with st.spinner('Processing your question...'):
            response = agent.run(question)
            st.markdown(response.content)


if __name__ == "__main__":
    main()
