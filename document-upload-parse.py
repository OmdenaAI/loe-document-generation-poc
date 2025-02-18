import streamlit as st
import docx
import json
import re
from io import BytesIO
import openai
import os

# Set OpenAI API key
openai.api_key = st.secrets.OPENAI_API_KEY #os.getenv("OPENAI_API_KEY")

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

st.title("📄 Document Upload & AI Placeholder Insertion")

# ✅ Extract text from DOCX
def extract_text_from_docx(docx_file):
    """Extract text from DOCX while preserving structure."""
    doc = docx.Document(docx_file)
    text = [para.text for para in doc.paragraphs]
    return "\n\n".join(text)

# ✅ Extract placeholders using regex
def extract_placeholders(text):
    """Extracts placeholders in ${variable-name} format."""
    if not text:
        return {}
    extracted = list(set(re.findall(r"\$\{(.*?)\}", text)))
    return {ph: {"type": "Text", "required": False, "is_conditional": False, "dependent_on": None} for ph in extracted}

# ✅ AI-based Placeholder Suggestion
def suggest_placeholders_with_ai(markdown_text):
    """Uses LLM to suggest additional placeholders and ensures JSON response."""
    prompt = f"""
    Extract missing placeholders from this document. Respond with ONLY a JSON in this format:
    
    {{
      "suggested_placeholders": {{
        "field1": "descriptive-name-1",
        "field2": "descriptive-name-2"
      }}
    }}
    
    **Rules:** 
    - Return ONLY JSON, no explanations.
    - Each key should be lowercase with hyphens.
    
    **Document:**
    {markdown_text}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an AI that must return JSON only. No extra text."},
                {"role": "user", "content": prompt}
            ]
        )

        # Extract and clean the response
        raw_response = response.choices[0].message.content.strip()

        # Debugging: Print raw response
        #st.write("🔍 OpenAI Raw Response:", raw_response)

        # Check for empty response
        if not raw_response:
            st.error("⚠️ OpenAI API returned an empty response.")
            return {}

        # Ensure response is valid JSON
        try:
            parsed_response = json.loads(raw_response)
        except json.JSONDecodeError:
            st.error("⚠️ OpenAI returned malformed JSON. Retrying with a simpler prompt...")
            return {}

        # Ensure the response contains expected structure
        if "suggested_placeholders" not in parsed_response:
            st.error("⚠️ OpenAI response did not contain 'suggested_placeholders'.")
            return {}

        # Format placeholders
        return {
            key: {
                "type": "Text",
                "required": False,
                "is_conditional": False,
                "dependent_on": None
            }
            for key in parsed_response["suggested_placeholders"].values()
        }

    except Exception as e:
        st.error(f"⚠️ OpenAI API error: {str(e)}")
        return {}


# ✅ Function to insert placeholders into Markdown
def insert_placeholders_in_markdown(markdown_text, placeholders):
    """Uses LLM to insert placeholders into Markdown."""
    placeholder_list = "\n".join([f"- {p}" for p in placeholders.keys()])
    
    prompt = f"""
    Insert these placeholders into the document:
    {placeholder_list}
    
    **Rules:**
    1. Keep existing placeholders in their positions.
    2. Insert new placeholders logically.
    3. Preserve Markdown formatting.
    
    **Document:**
    {markdown_text}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "Return the formatted Markdown document."},
                      {"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"⚠️ OpenAI API error: {str(e)}")
        return markdown_text

# ✅ Convert Markdown to DOCX
def convert_markdown_to_docx(markdown_text, output_path="updated_template.docx"):
    """Converts Markdown text to DOCX format."""
    doc = docx.Document()
    lines = markdown_text.split("\n")
    
    for line in lines:
        if line.startswith('#'):
            level = line.count('#')
            text = line.lstrip('#').strip()
            doc.add_paragraph(text, style=f'Heading {min(level, 9)}')
        else:
            doc.add_paragraph(line)
    
    doc.save(output_path)
    return output_path

# ✅ Handle file upload
uploaded_file = st.file_uploader("Upload a DOCX file", type=["docx"])

if uploaded_file and not st.session_state.processed_text:
    st.session_state.processed_text = extract_text_from_docx(uploaded_file)
    
    # Extract existing placeholders
    st.session_state.placeholders = extract_placeholders(st.session_state.processed_text)
    
    # Get AI suggestions
    if not st.session_state.ai_suggestions:
        st.write("🤖 AI is analyzing the document...")
        st.session_state.ai_suggestions = suggest_placeholders_with_ai(st.session_state.processed_text)

# ✅ Configure extracted placeholders
st.markdown("### 📝 Existing Placeholders")
for ph, settings in st.session_state.placeholders.items():
    st.markdown(f"#### {ph}")
    settings["type"] = st.selectbox("Type", ["Text", "Date", "Number"], key=f"dt_{ph}")
    settings["required"] = st.checkbox("📍 Required", key=f"req_{ph}")
    settings["is_conditional"] = st.checkbox("🔗 Conditional", key=f"cond_{ph}")

    # ✅ Show "Depends on" only if Conditional is checked
    if settings["is_conditional"]:
        all_placeholders_list = list(st.session_state.placeholders.keys()) + list(st.session_state.accepted_ai_suggestions.keys())
        settings["dependent_on"] = st.selectbox("Depends on:", ["None"] + all_placeholders_list, key=f"dep_{ph}")

# ✅ Accept AI-suggested placeholders
st.markdown("### 🧠 AI-Suggested Placeholders")
for ph in st.session_state.ai_suggestions.keys():
    accept = st.checkbox(f"✅ Accept: {ph}", key=f"accept_{ph}")
    if accept:
        settings = {
            "type": st.selectbox("Type", ["Text", "Date", "Number"], key=f"dt_ai_{ph}"),
            "required": st.checkbox("📍 Required", key=f"req_ai_{ph}"),
            "is_conditional": st.checkbox("🔗 Conditional", key=f"cond_ai_{ph}"),
            "dependent_on": None  # Initially None
        }

        # ✅ Show "Depends on" only if Conditional is checked
        if settings["is_conditional"]:
            all_placeholders_list = list(st.session_state.placeholders.keys()) + list(st.session_state.accepted_ai_suggestions.keys())
            settings["dependent_on"] = st.selectbox("Depends on:", ["None"] + all_placeholders_list, key=f"dep_ai_{ph}")

        st.session_state.accepted_ai_suggestions[ph] = settings

# ✅ Merge placeholders for JSON & Markdown
all_placeholders = {**st.session_state.placeholders, **st.session_state.accepted_ai_suggestions}

if st.button("💾 Save Template"):
    # ✅ Merge placeholders for JSON & Markdown
    all_placeholders = {**st.session_state.placeholders, **st.session_state.accepted_ai_suggestions}

    # ✅ Save template as JSON
    with open("template.json", "w") as f:
        json.dump({"placeholders": all_placeholders}, f, indent=4)
    st.success("✅ Template saved!")

    # ✅ Determine if AI suggestions were accepted
    if st.session_state.accepted_ai_suggestions:
        st.write("🔹 AI placeholders accepted – updating document...")
        updated_markdown = insert_placeholders_in_markdown(st.session_state.processed_text, all_placeholders)
    else:
        st.write("✅ No AI placeholders accepted – using extracted placeholders only.")
        updated_markdown = st.session_state.processed_text

    # ✅ Save updated Markdown
    st.session_state.processed_text = updated_markdown
    markdown_bytes = BytesIO(updated_markdown.encode("utf-8"))
    st.download_button("📥 Download Markdown", markdown_bytes, "updated_template.md", "text/markdown")

    # ✅ Convert to DOCX
    updated_doc_path = convert_markdown_to_docx(updated_markdown)
    with open(updated_doc_path, "rb") as doc_file:
        st.download_button("📥 Download Updated DOCX", doc_file, "updated_template.docx",
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")