import streamlit as st
import pdfplumber
import docx
import re
import json
import os
import openai
from io import BytesIO


# Set OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")  # Ensure API key is set in your environment

# Initialize session state for template data and AI suggestions
if "template_data" not in st.session_state:
    st.session_state.template_data = None

if "ai_suggestions" not in st.session_state:
    st.session_state.ai_suggestions = {}

# Initialize additional session state variables
if "processed_text" not in st.session_state:
    st.session_state.processed_text = None
if "placeholders" not in st.session_state:
    st.session_state.placeholders = {}
if "ai_analysis_complete" not in st.session_state:
    st.session_state.ai_analysis_complete = False

st.title("📄 Document Upload & Placeholder Extraction (with AI & Dependencies)")

# ✅ Function to extract text from DOCX
def extract_text_from_docx(file):
    doc = docx.Document(file)
    return "\n".join([para.text for para in doc.paragraphs])

# ✅ Function to extract text from PDF
def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

# ✅ Function to extract placeholders using regex
def extract_placeholders(text):
    """Extracts unique placeholders while maintaining order."""
    seen = set()
    placeholders = []
    
    for match in re.findall(r"\{(.*?)\}", text):  # Extract placeholders like {Name}, {Date}
        if match not in seen:
            seen.add(match)
            placeholders.append(match)

    return placeholders

# ✅ Function to convert placeholder names into human-readable format
def format_placeholder_name(name):
    """Converts placeholders like 'AgeofReceipt' into 'Age of Receipt'."""
    name = re.sub(r'(?<!^)(?=[A-Z])', ' ', name)  # Insert space before capital letters
    name = name.replace("_", " ")  # Replace underscores with spaces
    return name.strip().title()  # Capitalize each word properly

# ✅ Function to get AI-suggested placeholders
def suggest_placeholders_with_ai(text):
    """Uses LLM to detect additional placeholders that may be missing."""
    
    prompt = f"""
    You are an AI assistant helping to extract placeholders from a document.
    You must respond with ONLY a JSON object in this exact format:
    {{
      "suggested_placeholders": {{
        "detected_text": "placeholder_name"
      }}
    }}

    Analyze this document and identify implied fields that should be placeholders:
    {text}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a JSON-only response AI. Never include explanations or text outside the JSON structure."},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" }  # Enforce JSON response
        )
        
        # Parse response
        parsed_response = json.loads(response.choices[0].message.content)
        return {k: format_placeholder_name(v) for k, v in parsed_response["suggested_placeholders"].items()}

    except Exception as e:
        st.error(f"⚠️ OpenAI API error: {str(e)}")
        return {}

# ✅ Save uploaded file for later use
def save_uploaded_file(uploaded_file, filename):
    with open(filename, "wb") as f:
        f.write(uploaded_file.getbuffer())

def update_template_docx(accepted_placeholders):
    """Updates template.docx with accepted AI suggestions"""
    try:
        doc = docx.Document("template.docx")
        for para in doc.paragraphs:
            text = para.text
            # Add curly braces around accepted AI suggestions
            for original, placeholder in accepted_placeholders.items():
                if original in text:
                    text = text.replace(original, f"{{{placeholder}}}")
            para.text = text
        doc.save("template_updated.docx")
        return True
    except Exception as e:
        st.error(f"Error updating template: {str(e)}")
        return False

# Handle file upload and initial processing
uploaded_file = st.file_uploader("Upload a Document (DOCX or PDF)", type=["docx", "pdf"])

if uploaded_file and not st.session_state.processed_text:
    # Save original template
    if uploaded_file.name.endswith(".docx"):
        save_uploaded_file(uploaded_file, "template.docx")
        text = extract_text_from_docx(uploaded_file)
    else:
        text = extract_text_from_pdf(uploaded_file)
    
    # Process text and store results in session state
    st.session_state.processed_text = text
    st.session_state.placeholders = {ph: format_placeholder_name(ph) 
                                   for ph in extract_placeholders(text)}
    
    # Get AI suggestions only once
    if not st.session_state.ai_analysis_complete:
        st.write("### 🤖 AI is analyzing the document...")
        st.session_state.ai_suggestions = suggest_placeholders_with_ai(text)
        st.session_state.ai_analysis_complete = True

# Display form only if we have processed text
if st.session_state.processed_text:
    st.markdown("""
    <style>
    .placeholder-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
    }
    .stExpander {
        border: 1px solid #ddd;
        border-radius: 8px;
        margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("### 📌 Configure Existing Placeholders")
    
    placeholder_settings = {}
    accepted_ai_suggestions = {}

    # Handle existing placeholders
    for ph, formatted_name in st.session_state.placeholders.items():
        st.markdown(f"""
        <div class="placeholder-card">
        <h4>{formatted_name}</h4>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            data_type = st.selectbox(
                "Type",
                ["Text", "Date", "Number", "Dropdown", "Checkbox"],
                key=f"dt_{ph}"
            )
        with col2:
            required = st.checkbox("📍 Required", key=f"req_{ph}")
        with col3:
            is_conditional = st.checkbox("🔗 Conditional", key=f"cond_{ph}")
        
        if is_conditional:
            st.markdown("##### Dependency Settings")
            dependent_on = st.selectbox(
                "This field depends on:",
                list(st.session_state.placeholders.values()),
                key=f"dep_{ph}"
            )
        else:
            dependent_on = None

        placeholder_settings[formatted_name] = {
            "type": data_type,
            "required": required,
            "is_conditional": is_conditional,
            "dependent_on": dependent_on
        }
        st.markdown("---")

    # Handle AI suggestions
    if st.session_state.ai_suggestions:
        st.markdown("### 🧠 AI-Suggested Placeholders")
        st.info("Review and configure additional fields detected by AI")
        
        for original_text, suggested_name in st.session_state.ai_suggestions.items():
            with st.expander(f"📍 **{suggested_name}** (detected from: '{original_text}')"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    accept_suggestion = st.checkbox("✅ Accept this suggestion", key=f"ai_accept_{suggested_name}")
                
                if accept_suggestion:
                    st.markdown("##### Configure Field")
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        data_type = st.selectbox(
                            "Type",
                            ["Text", "Date", "Number", "Dropdown", "Checkbox"],
                            key=f"ai_dt_{suggested_name}"
                        )
                    with col2:
                        required = st.checkbox("📍 Required", key=f"ai_req_{suggested_name}")
                    with col3:
                        is_conditional = st.checkbox("🔗 Conditional", key=f"ai_cond_{suggested_name}")
                    
                    if is_conditional:
                        st.markdown("##### Dependency Settings")
                        dependent_on = st.selectbox(
                            "This field depends on:",
                            list(st.session_state.placeholders.values()),
                            key=f"ai_dep_{suggested_name}"
                        )
                    else:
                        dependent_on = None

                    placeholder_settings[suggested_name] = {
                        "type": data_type,
                        "required": required,
                        "is_conditional": is_conditional,
                        "dependent_on": dependent_on
                    }
                    accepted_ai_suggestions[original_text] = suggested_name

    # Save button section
    st.markdown("---")
    st.markdown("### 💾 Save Configuration")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("Save Template", use_container_width=True):
            # Save template.json
            template_data = {"placeholders": placeholder_settings}
            with open("template.json", "w") as f:
                json.dump(template_data, f, indent=4)
            
            # Update template.docx with AI suggestions if any were accepted
            if accepted_ai_suggestions and update_template_docx(accepted_ai_suggestions):
                st.success("✅ Template and document updated successfully!")
                
                # Provide download buttons
                col1, col2 = st.columns(2)
                with col1:
                    with open("template.json", "rb") as f:
                        st.download_button(
                            "📥 Download Template JSON",
                            f,
                            file_name="template.json",
                            mime="application/json",
                            use_container_width=True
                        )
                with col2:
                    with open("template_updated.docx", "rb") as f:
                        st.download_button(
                            "📥 Download Updated Document",
                            f,
                            file_name="template.docx",
                            use_container_width=True
                        )
