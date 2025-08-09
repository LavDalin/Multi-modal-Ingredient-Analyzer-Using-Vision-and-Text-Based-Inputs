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
            "Analyze the given image and extract the ingredients",
            images=[image_path],
        )
        st.session_state.ingredients = response.content
        st.markdown(response.content)

# Main app logic
def main():
    st.title("🔍 Product Ingredient Analyzer")
    
    # Session state to manage previous user selections
    if 'selected_example' not in st.session_state:
        st.session_state.selected_example = None
    if 'analyze_clicked' not in st.session_state:
        st.session_state.analyze_clicked = False
    if 'ingredients' not in st.session_state:
        st.session_state.ingredients = None  # Store ingredients info

    tab_examples, tab_upload, tab_camera = st.tabs([
        "📚 Example Products",
        "📤 Upload Image",
        "📸 Take Photo"
    ])

    with tab_examples:
        example_images = {
            "🍫 Chocolate Bar": "Images/Chocolate.png",
            "🥤 Bournvita": "Images/Bournvita.png",
            "🥔 Potato Chips": "Images/Chips.png",
            "🧴 Shampoo": "Images/Shampoo.png"
        }
        
        cols = st.columns(4)
        for idx, (name, path) in enumerate(example_images.items()):
            with cols[idx]:
                if st.button(name, use_container_width=True):
                    st.session_state.selected_example = path
                    st.session_state.analyze_clicked = False

    with tab_upload:
        uploaded_file = st.file_uploader(
            "Upload product image",
            type=["jpg", "jpeg", "png"],
            help="Upload a clear image of the product's ingredient list"
        )
        if uploaded_file:
            resized_image = resize_image_for_display(uploaded_file)
            st.image(resized_image, caption="Uploaded Image", use_container_width=False, width=MAX_IMAGE_WIDTH)
            if st.button("🔍 Analyze Uploaded Image", key="analyze_upload"):
                temp_path = save_uploaded_file(uploaded_file)
                analyze_image(temp_path)
                os.unlink(temp_path)
    
    with tab_camera:
        camera_photo = st.camera_input("Take a picture of the product")
        if camera_photo:
            resized_image = resize_image_for_display(camera_photo)
            st.image(resized_image, caption="Captured Photo", use_container_width=False, width=MAX_IMAGE_WIDTH)
            if st.button("🔍 Analyze Captured Photo", key="analyze_camera"):
                temp_path = save_uploaded_file(camera_photo)
                analyze_image(temp_path)
                os.unlink(temp_path)
    
    if st.session_state.selected_example:
        st.divider()
        st.subheader("Selected Product")
        resized_image = resize_image_for_display(st.session_state.selected_example)
        st.image(resized_image, caption="Selected Example", use_container_width=False, width=MAX_IMAGE_WIDTH)
        
        if st.button("🔍 Analyze Example", key="analyze_example") and not st.session_state.analyze_clicked:
            st.session_state.analyze_clicked = True
            analyze_image(st.session_state.selected_example)

    # Ask users for more questions
    st.subheader("Ask More Questions")
    user_question = st.text_input("Ask a question about the product or ingredients:")

    if user_question:
        if st.session_state.ingredients:
            # If ingredients were extracted, pass them into the prompt
            question = f"Given the ingredients extracted: {st.session_state.ingredients}, {user_question}"
        else:
            question = user_question  # Otherwise, just ask the question

        agent = get_agent()
        with st.spinner('Processing your question...'):
            response = agent.run(question)
            st.markdown(response.content)

if __name__ == "__main__":
    main()
