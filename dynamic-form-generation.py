import streamlit as st
import json
import os
import docx
import openai
from datetime import datetime

# Set OpenAI API Key
openai.api_key = os.getenv("OPENAI_API_KEY")

st.title("📝 Dynamic Form & AI-Powered Document Generation")

# ✅ Load template JSON
template_path = "template.json"
if not os.path.exists(template_path):
    st.error("❌ Missing `template.json`. Please complete the document upload step first.")
    st.stop()

with open(template_path, "r") as f:
    template_data = json.load(f)

placeholders = template_data.get("placeholders", {})

# ✅ Initialize session state for form data if not exists
if "form_data" not in st.session_state:
    # Store form data without ${} in keys but keep mapping to original names
    st.session_state.form_data = {key.strip("${}"): None for key in placeholders}

# ✅ Function to check if a dependent field should be shown
def should_show_field(field_name, field_info):
    """Returns True if a field should be displayed based on its dependencies."""
    if not field_info.get("is_conditional"):
        return True  # Show non-conditional fields
    
    dependent_on = field_info.get("dependent_on")
    if not dependent_on:
        return True  # If no dependency, show field

    # Convert dependent field name to match stripped internal representation
    dependent_field = dependent_on.strip("${}")
    parent_value = st.session_state.form_data.get(dependent_field)

    # Show the field only if the parent field is filled
    return parent_value not in [None, "", [], False]

# ✅ Dynamic Form UI
st.write("### ✏️ Fill out the form below:")
form_data = {}

# Update the form generation loop to properly check dependencies
for field_name_with_syntax, field_info in placeholders.items():
    field_name = field_name_with_syntax.strip("${}")  # Remove ${} syntax for internal use

    if should_show_field(field_name, field_info):  # Only show if conditions are met
        label = f"{field_name} {'*' if field_info['required'] else ''}"

        # ✅ Handle different field types
        if field_info["type"] == "Text":
            form_data[field_name] = st.text_input(label, key=f"input_{field_name}")
        elif field_info["type"] == "Number":
            form_data[field_name] = st.number_input(label, key=f"input_{field_name}")
        elif field_info["type"] == "Date":
            selected_date = st.date_input(label, key=f"input_{field_name}")
            form_data[field_name] = selected_date.strftime('%Y-%m-%d')
        elif field_info["type"] == "Dropdown":
            options = ["Option 1", "Option 2", "Option 3"]
            form_data[field_name] = st.selectbox(label, options, key=f"input_{field_name}")
        elif field_info["type"] == "Checkbox":
            form_data[field_name] = st.checkbox(label, key=f"input_{field_name}")
        else:
            form_data[field_name] = st.text_input(label, key=f"input_{field_name}")

        # Store updated values in session state
        st.session_state.form_data[field_name] = form_data[field_name]

# ✅ Function to validate required fields
def validate_form():
    """Ensures all required fields are filled before saving."""
    missing_fields = [
        name.strip("${}") for name, info in placeholders.items()
        if info["required"] and not form_data.get(name.strip("${}"))
    ]
    
    if missing_fields:
        st.error(f"⚠️ Please fill in all required fields: {', '.join(missing_fields)}")
        return False
    return True

# ✅ Document Generation Logic
if st.button("📥 Download Final Document"):
    if validate_form():
        # Save filled data
        with open("filled_data.json", "w") as f:
            json.dump(form_data, f, indent=4)

        try:
            doc = docx.Document("template.docx")
            
            # Replace placeholders in each paragraph
            for para in doc.paragraphs:
                text = para.text
                for field_name, value in form_data.items():
                    if value is not None:
                        # Convert boolean values to Yes/No
                        if isinstance(value, bool):
                            value = "Yes" if value else "No"
                        # Ensure the placeholder is replaced properly
                        text = text.replace(f"${{{field_name}}}", str(value))
                para.text = text
            
            # Save the updated document
            output_path = "final_document.docx"
            doc.save(output_path)
            
            st.success("✅ Document generated successfully!")

            # Provide download button
            with open(output_path, "rb") as f:
                st.download_button(
                    "📥 Download Completed Document",
                    f,
                    file_name="final_document.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
        except Exception as e:
            st.error(f"❌ Error generating document: {str(e)}")
