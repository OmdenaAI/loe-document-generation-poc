import streamlit as st
import pdfplumber
import docx
import re
import json
import os
import openai
from io import BytesIO

# Set OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Initialize session state
if "template_data" not in st.session_state:
    st.session_state.template_data = None

if "ai_suggestions" not in st.session_state:
    st.session_state.ai_suggestions = {}

if "accepted_ai_suggestions" not in st.session_state:
    st.session_state.accepted_ai_suggestions = {}

if "placeholders" not in st.session_state:
    st.session_state.placeholders = {}

if "processed_text" not in st.session_state:
    st.session_state.processed_text = None

st.title("📄 Document Upload & Placeholder Extraction (with AI & Dependencies)")

# ✅ Function to extract text from DOCX
def extract_text_from_docx(file):
    doc = docx.Document(file)
    return "\n".join([para.text for para in doc.paragraphs])

# ✅ Function to extract existing placeholders using regex
def extract_placeholders(text):
    """Extracts existing placeholders in ${variable-name} format."""
    return list(set(re.findall(r"\$\{(.*?)\}", text)))

# ✅ Function to get AI-suggested placeholders
def suggest_placeholders_with_ai(text):
    """Uses LLM to detect additional placeholders that may be missing."""
    
    prompt = f"""
    You are an AI assistant helping to extract placeholders from a document.
    You must respond with ONLY a JSON object in this exact format:
    {{"suggested_placeholders": {{"detected_text": "variable-name"}}}}

    Analyze this document and identify implied fields that should be placeholders:
    {text}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "system", "content": "You are a JSON-only response AI. Never include explanations or text outside the JSON structure."},
                      {"role": "user", "content": prompt}]
        )
        
        # Parse response
        parsed_response = json.loads(response.choices[0].message.content)
        return {k: f"${{{v}}}" for k, v in parsed_response["suggested_placeholders"].items()}  # ✅ Ensure ${variable-name} format

    except Exception as e:
        st.error(f"⚠️ OpenAI API error: {str(e)}")
        return {}

# Add this new function after suggest_placeholders_with_ai
def get_llm_placeholder_positions(text, placeholders):
    """Uses LLM to determine where to place accepted placeholders in the document."""
    
    prompt = f"""
    You are an AI assistant helping to place placeholders in a document.
    Place these placeholders in appropriate positions in the document: {list(placeholders.keys())}
    
    Rules:
    1. Keep all existing placeholders in their current positions
    2. Place new placeholders where they make logical sense
    3. Use the exact format ${{placeholder_name}} for each placeholder
    4. Return the complete document with all placeholders properly placed
    
    Original document:
    {text}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a document formatting AI. Return only the formatted document text."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"⚠️ OpenAI API error: {str(e)}")
        return text

# Update the insert_placeholders_in_docx function
def insert_placeholders_in_docx(doc_path, placeholders):
    """Inserts AI-suggested & user-defined placeholders into the document."""
    doc = docx.Document(doc_path)
    text = "\n".join([para.text for para in doc.paragraphs])
    
    # Get LLM suggestions for placeholder positions
    formatted_text = get_llm_placeholder_positions(text, placeholders)
    
    # Create new document with formatted text
    new_doc = docx.Document()
    for paragraph in formatted_text.split('\n'):
        if paragraph.strip():
            new_doc.add_paragraph(paragraph)
    
    new_doc.save("template.docx")
    return "template.docx"

# ✅ Save uploaded file for later use
def save_uploaded_file(uploaded_file, filename):
    with open(filename, "wb") as f:
        f.write(uploaded_file.getbuffer())

# Handle file upload and initial processing
uploaded_file = st.file_uploader("Upload a Document (DOCX)", type=["docx"])

if uploaded_file and not st.session_state.processed_text:
    # Save original template
    save_uploaded_file(uploaded_file, "original_template.docx")
    text = extract_text_from_docx(uploaded_file)

    # Process text and store results in session state
    st.session_state.processed_text = text
    st.session_state.placeholders = {ph: f"${{{ph}}}" for ph in extract_placeholders(text)}
    
    # Get AI suggestions only once
    if not st.session_state.ai_suggestions:
        st.write("### 🤖 AI is analyzing the document...")
        st.session_state.ai_suggestions = suggest_placeholders_with_ai(text)

# ✅ Ensure all placeholders (existing & AI-suggested) are reviewed before inclusion
st.markdown("### 📌 Configure Placeholders (Existing & AI-Suggested)")
placeholder_settings = {}

# ✅ Merge manually extracted and AI-suggested placeholders into a unified list
all_placeholders = {**st.session_state.placeholders, **st.session_state.accepted_ai_suggestions}
all_placeholder_names = list(all_placeholders.keys())

# ✅ Configure Existing Placeholders
st.markdown("### 📝 Existing Placeholders (Automatically Extracted)")
for ph, formatted_name in st.session_state.placeholders.items():
    st.markdown(f"#### {formatted_name}")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        data_type = st.selectbox("Type", ["Text", "Date", "Number", "Dropdown", "Checkbox"], key=f"dt_{ph}")
    with col2:
        required = st.checkbox("📍 Required", key=f"req_{ph}")
    with col3:
        is_conditional = st.checkbox("🔗 Conditional", key=f"cond_{ph}")

    dependent_on = None
    if is_conditional:
        dependent_on = st.selectbox(
            "This field depends on:",
            all_placeholder_names,
            key=f"dep_{ph}"
        )

    placeholder_settings[formatted_name] = {
        "type": data_type,
        "required": required,
        "is_conditional": is_conditional,
        "dependent_on": dependent_on
    }

# ✅ Handle AI suggestions (Accept or Reject)
st.markdown("### 🧠 AI-Suggested Placeholders")
for ph, formatted_name in st.session_state.ai_suggestions.items():
    accept = st.checkbox(f"✅ Accept: {formatted_name}", key=f"accept_{ph}")

    if accept:
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            data_type = st.selectbox("Type", ["Text", "Date", "Number", "Dropdown", "Checkbox"], key=f"dt_ai_{ph}")
        with col2:
            required = st.checkbox("📍 Required", key=f"req_ai_{ph}")
        with col3:
            is_conditional = st.checkbox("🔗 Conditional", key=f"cond_ai_{ph}")

        dependent_on = None
        if is_conditional:
            dependent_on = st.selectbox(
                "This field depends on:",
                all_placeholder_names,
                key=f"dep_ai_{ph}"
            )

        st.session_state.accepted_ai_suggestions[formatted_name] = {
            "type": data_type,
            "required": required,
            "is_conditional": is_conditional,
            "dependent_on": dependent_on
        }

st.markdown("---")

# ✅ Save button section
st.markdown("### 💾 Save Configuration")
if st.button("Save Template"):
    # Save the template configuration
    template_data = {"placeholders": {**placeholder_settings, **st.session_state.accepted_ai_suggestions}}
    with open("template.json", "w") as f:
        json.dump(template_data, f, indent=4)
    
    # ✅ Insert accepted AI & user-defined placeholders into DOCX
    if uploaded_file:
        placeholder_mapping = {**st.session_state.placeholders, **{k: f"${{{k}}}" for k in st.session_state.accepted_ai_suggestions.keys()}}
        updated_doc_path = insert_placeholders_in_docx("original_template.docx", placeholder_mapping)
        st.success("✅ Template configuration saved and document updated!")

        # Provide preview of the formatted document
        st.markdown("### 📄 Preview of Formatted Document")
        with open(updated_doc_path, "rb") as f:
            st.download_button("📥 Download Updated Template", f, file_name="template.docx")

    else:
        st.success("✅ Template configuration saved!")
