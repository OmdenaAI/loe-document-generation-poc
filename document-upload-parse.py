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

# ✅ Extract text from DOCX and convert to Markdown
# ✅ Extract text from DOCX and convert to Markdown
def extract_text_from_docx(docx_file):
    """Extract text from DOCX and preserve basic formatting."""
    doc = docx.Document(docx_file)
    text = []
    
    for para in doc.paragraphs:
        if para.style.name.startswith('Heading'):
            level = para.style.name[-1]
            text.append(f"{'#' * int(level)} {para.text}")
        else:
            text.append(para.text)
    
    return "\n\n".join(text)

def convert_markdown_to_docx(markdown_text, output_path="updated_template.docx"):
    """Converts Markdown text to a formatted DOCX document."""
    doc = docx.Document()
    
     # ✅ Fix: Remove unnecessary Markdown fencing (e.g., ```markdown)
    markdown_text = re.sub(r"^```[a-zA-Z]*\n", "", markdown_text, flags=re.MULTILINE)  # Remove opening triple backticks
    markdown_text = re.sub(r"\n```$", "", markdown_text, flags=re.MULTILINE)  # Remove closing triple backticks
    
    # Split the markdown text into lines
    lines = markdown_text.split('\n')
    
    for line in lines:
        if line.strip():  # Skip empty lines
            # Check for headings
            if line.startswith('#'):
                level = len(line.split()[0])  # Count the number of #
                text = line.lstrip('#').strip()
                doc.add_paragraph(text, style=f'Heading {min(level, 9)}')
            else:
                # Regular paragraph
                doc.add_paragraph(line)
    
    # Save the document
    doc.save(output_path)
    return output_path

# ✅ Function to extract existing placeholders using regex
def extract_placeholders(text):
    """Extracts existing placeholders in ${variable-name} format and ensures uniform structure."""
    if not text:  # Handle NoneType or empty string
        return {}
    extracted_placeholders = list(set(re.findall(r"\$\{(.*?)\}", text)))
    
    # Format placeholders in the same structure as AI suggestions
    formatted_placeholders = {
        ph: {
            "type": "Text",  # Default type
            "required": False,  # Default required value
            "is_conditional": False,  # Default conditional status
            "dependent_on": None  # Default no dependency
        }
        for ph in extracted_placeholders
    }
    
    return formatted_placeholders

# ✅ Function to get AI-suggested placeholders
def suggest_placeholders_with_ai(markdown_text):
    """Uses LLM to detect additional placeholders that may be missing."""
    
    prompt = f"""
    You are an AI assistant helping to extract placeholders from a document.
    You must respond with ONLY a JSON object in this exact format:
    {{"suggested_placeholders": {{
        "field1": "descriptive-name-1",
        "field2": "descriptive-name-2"
    }}}}
    
    Rules:
    1. Each field should be a separate key-value pair
    2. Use lowercase with hyphens for variable names
    3. Do not include ${{}} in the names
    4. Each detected field should be its own entry
    5. Do not return a list of fields
    
    Analyze this document and identify implied fields that should be placeholders:
    {markdown_text}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",  # Changed back to original model
            messages=[
                {"role": "system", "content": "You are a JSON-only response AI. Never include explanations or text outside the JSON structure."},
                {"role": "user", "content": prompt}
            ]
        )
        
        # Parse response and format each placeholder separately
        parsed_response = json.loads(response.choices[0].message.content)
        return {
            k: f"${{{v.lower().replace(' ', '-').replace('_', '-')}}}" 
            for k, v in parsed_response["suggested_placeholders"].items()
        }

    except Exception as e:
        st.error(f"⚠️ OpenAI API error: {str(e)}")
        return {}

# Add this new function after suggest_placeholders_with_ai
def get_llm_placeholder_positions(text, placeholders):
    """Uses LLM to determine where to place accepted placeholders in the document."""
    
    # Convert placeholders to a formatted string list
    placeholder_list = "\n".join([f"- ${{{p.strip('${}')}}} " for p in placeholders])
    
    prompt = f"""
    You are an AI assistant helping to place placeholders in a document.
    Place these placeholders in appropriate positions in the document:
    {placeholder_list}
    
    Rules:
    1. Keep all existing placeholders in their current positions
    2. Place new placeholders where they make logical sense
    3. Use each placeholder exactly as provided above (e.g., ${{{placeholder_list.split()[0].strip('- ')}}})
    4. Place each placeholder separately, do not combine them into a list
    5. Return the complete document with all placeholders properly placed
    
    Original document:
    {text}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4-mini",
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
def insert_placeholders_in_markdown(markdown_text, placeholders):
    """Uses LLM to insert placeholders into Markdown text properly."""
    
    placeholder_list = "\n".join([f"- {p}" for p in placeholders.keys()])
    
    prompt = f"""
    You are an AI assistant improving a document by inserting placeholders.
    Place these placeholders where they logically belong:
    {placeholder_list}
    
    **Rules:**
    1. Keep existing placeholders in their current positions.
    2. Place new placeholders where they make sense.
    3. Preserve the original Markdown structure.
    4. Use the exact placeholder format, e.g., `${{variable-name}}`.
    5. Return ONLY the updated Markdown document.

    **Original Markdown:**
    {markdown_text}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a document formatting AI. Return only the formatted Markdown."},
                      {"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

    except Exception as e:
        st.error(f"⚠️ OpenAI API error: {str(e)}")
        return markdown_text  # Return original if error occurs

# ✅ Save uploaded file for later use
def save_uploaded_file(uploaded_file, filename):
    with open(filename, "wb") as f:
        f.write(uploaded_file.getbuffer())

# Handle file upload and initial processing
uploaded_file = st.file_uploader("Upload a Document (DOCX)", type=["docx"])

if uploaded_file and not st.session_state.processed_text:
    st.session_state.processed_text = extract_text_from_docx(uploaded_file)
    # Save original template
    save_uploaded_file(uploaded_file, "original_template.docx")
    markdown_output = extract_text_from_docx(uploaded_file)

    # Store in session state
    st.session_state.processed_text = markdown_output
    st.session_state.placeholders = {ph: f"${{{ph}}}" for ph in extract_placeholders(markdown_output)}
    # Process text and store results in session state
    st.session_state.processed_text = markdown_output
    st.session_state.placeholders = {ph: f"${{{ph}}}" for ph in extract_placeholders(markdown_output)}
    
    # Get AI suggestions only once
    if not st.session_state.ai_suggestions:
        st.write("### 🤖 AI is analyzing the document...")
        st.session_state.ai_suggestions = suggest_placeholders_with_ai(markdown_output)

# ✅ Ensure all placeholders (existing & AI-suggested) are reviewed before inclusion
st.markdown("### 📌 Configure Placeholders (Existing & AI-Suggested)")

# ✅ Merge manually extracted and AI-suggested placeholders into a unified list
all_placeholders = {
    **extract_placeholders(st.session_state.processed_text),  # Extracted placeholders with default values
    **st.session_state.accepted_ai_suggestions  # AI-suggested placeholders
}
all_placeholder_names = list(all_placeholders.keys())

# ✅ Configure Existing Placeholders
st.markdown("### 📝 Existing Placeholders (Automatically Extracted)")
for ph, settings in all_placeholders.items():
    st.markdown(f"#### {ph}")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        data_type = st.selectbox("Type", ["Text", "Date", "Number", "Dropdown", "Checkbox"], 
                                 key=f"dt_{ph}", index=["Text", "Date", "Number", "Dropdown", "Checkbox"].index(settings["type"]))
    with col2:
        required = st.checkbox("📍 Required", value=settings["required"], key=f"req_{ph}")
    with col3:
        is_conditional = st.checkbox("🔗 Conditional", value=settings["is_conditional"], key=f"cond_{ph}")

    dependent_on = None
    if is_conditional:
        dependent_on = st.selectbox(
            "This field depends on:",
            ["None"] + all_placeholder_names,  # Allow user to select 'None'
            index=(["None"] + all_placeholder_names).index(settings["dependent_on"]) if settings["dependent_on"] else 0,
            key=f"dep_{ph}"
        )
        dependent_on = None if dependent_on == "None" else dependent_on

    # ✅ Update the placeholder settings with user inputs
    all_placeholders[ph] = {
        "type": data_type,
        "required": required,
        "is_conditional": is_conditional,
        "dependent_on": dependent_on
    }

# ✅ Handle AI suggestions (Accept or Reject)
st.markdown("### 🧠 AI-Suggested Placeholders")
for ph, formatted_name in st.session_state.ai_suggestions.items():
    accept = st.checkbox(f"✅ Accept: {formatted_name}", key=f"accept_{ph}")
    st.write(formatted_name)
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
    # ✅ Ensure all user modifications are properly saved
    template_data = {"placeholders": all_placeholders}

    with open("template.json", "w") as f:
        json.dump(template_data, f, indent=4)

    st.success("✅ Template configuration saved correctly with a consistent format!")

    # Ensure markdown_output exists in session
    if "processed_text" in st.session_state:
        markdown_output = st.session_state.processed_text  # Retrieve stored Markdown

               # ✅ Determine whether to use LLM
        if len(st.session_state.accepted_ai_suggestions) > 0:
            st.write("🔹 AI placeholders accepted – Using LLM to insert them...")
            try:
                placeholder_mapping = {
                    **st.session_state.placeholders,  # Keep document's extracted placeholders
                    **{k: f"${{{k}}}" for k in st.session_state.accepted_ai_suggestions.keys()}
                }
                markdown_output = insert_placeholders_in_markdown(markdown_output, placeholder_mapping)

                # ✅ Store updated Markdown in session state
                st.session_state.processed_text = markdown_output
                
            except Exception as e:
                st.error(f"⚠️ Error inserting AI placeholders: {str(e)}")
        
        else:
            st.write("✅ No AI placeholders accepted – Using extracted placeholders only.")

            st.success("✅ Template configuration saved and Markdown updated!")

            # ✅ Show preview of updated Markdown
            st.markdown("### 📝 Updated Markdown with Placeholders")
            st.text_area("Updated Document", markdown_output, height=400)

            # ✅ Allow user to download updated Markdown
            markdown_bytes = BytesIO(markdown_output.encode("utf-8"))
            st.download_button("📥 Download Updated Markdown", markdown_bytes, file_name="updated_template.md", mime="text/markdown")

            # ✅ Convert Markdown to DOCX
            updated_doc_path = convert_markdown_to_docx(markdown_output)

            # ✅ Allow user to download the updated DOCX file
            with open(updated_doc_path, "rb") as doc_file:
                st.download_button(
                    "📥 Download Updated DOCX",
                    doc_file,
                    file_name="updated_template.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
    else:
        st.error("⚠️ No document has been uploaded or processed yet.")
