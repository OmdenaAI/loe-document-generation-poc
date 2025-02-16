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
    st.session_state.form_data = {key: None for key in placeholders}

# ✅ Function to check if a dependent field should be shown
def should_show_field(field_name):
    """Returns True if a field should be displayed based on its dependencies."""
    field_info = placeholders.get(field_name, {})
    if not field_info.get("is_conditional"):
        return True  # Always show non-conditional fields
    
    dependent_on = field_info.get("dependent_on")
    if not dependent_on:
        return True  # If no parent field, show field

    # Check if the parent field is filled
    parent_value = st.session_state.form_data.get(dependent_on)
    return parent_value not in [None, "", [], False]  # Show field if parent is filled

# ✅ Dynamic Form UI
st.write("### ✏️ Fill out the form below:")
form_data = {}

for field_name, field_info in placeholders.items():
    if should_show_field(field_name):  # Only show if conditions are met
        label = f"{field_name} {'*' if field_info['required'] else ''}"

        # ✅ Handle different field types
        if field_info["type"] == "Text":
            form_data[field_name] = st.text_input(label, key=f"input_{field_name}")
        elif field_info["type"] == "Number":
            form_data[field_name] = st.number_input(label, key=f"input_{field_name}")
        elif field_info["type"] == "Date":
            selected_date = st.date_input(label, key=f"input_{field_name}")
            form_data[field_name] = selected_date.strftime('%Y-%m-%d')  # ✅ Convert date to string format
        elif field_info["type"] == "Dropdown":
            options = ["Option 1", "Option 2", "Option 3"]
            form_data[field_name] = st.selectbox(label, options, key=f"input_{field_name}")
        elif field_info["type"] == "Checkbox":
            form_data[field_name] = st.checkbox(label, key=f"input_{field_name}")
        else:
            form_data[field_name] = st.text_input(label, key=f"input_{field_name}")

        # ✅ Store updated values in session state
        st.session_state.form_data[field_name] = form_data[field_name]

# ✅ Validate required fields before saving
def validate_form():
    """Ensures all required fields are filled before saving."""
    missing_fields = [name for name, info in placeholders.items() if info["required"] and not form_data.get(name)]
    
    if missing_fields:
        st.error(f"⚠️ Please fill in all required fields: {', '.join(missing_fields)}")
        return False
    return True

# ✅ Save form data and generate the final document
if st.button("📥 Download Final Document"):
    if validate_form():
        # ✅ Convert all date fields to string format before saving to JSON
        for field_name, field_value in form_data.items():
            if isinstance(field_value, datetime):
                form_data[field_name] = field_value.strftime('%Y-%m-%d')

        # ✅ Save filled data
        with open("filled_data.json", "w") as f:
            json.dump(form_data, f, indent=4)
        
        # ✅ Generate final document with replaced placeholders
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
                        # Replace placeholder with value
                        text = text.replace(f"{{{field_name}}}", str(value))
                para.text = text
            
            # Save the updated document
            output_path = "final_document.docx"
            doc.save(output_path)
            
            # Provide download button
            with open(output_path, "rb") as f:
                st.download_button(
                    "📥 Download Completed Document",
                    f,
                    file_name="final_document.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            st.success("✅ Document generated successfully!")
            
        except Exception as e:
            st.error(f"❌ Error generating document: {str(e)}")
