# loe-document-generation-poc

Notes before running the script:
1- Run `document-uploader.py` to upload the document to extract placeholders and download the template.json file.
2- Run `dynamic-form-generator.py` which will load the template.json file(it should be in the root directory) and generate a dynamic form using Streamlit, then download the final document.



## **📜 AI-Powered Document Generation with Streamlit**
This project enables users to **upload a document with placeholders**, dynamically **fill a form based on the placeholders**, and **generate a final document** with AI assistance while preserving formatting.

---

## **📌 Features**
✅ **Upload DOCX/PDF templates with placeholders**  
✅ **Extract placeholders automatically & suggest missing ones using AI**  
✅ **Dynamically generate a form based on placeholders**  
✅ **Handle conditional dependencies between fields**  
✅ **Validate required fields before submission**  
✅ **Replace placeholders in the final document**  
✅ **Generate AI-enhanced documents preserving original formatting**  
✅ **Download the final document as a Word file**  

---

## **🚀 Installation**
### **1️⃣ Clone the Repository**
```sh
git clone https://github.com/loe-document-generation-poc.git
cd loe-document-generation-poc
```

### **2️⃣ Set Up a Virtual Environment (Recommended)**
#### **On Windows (PowerShell)**
```sh
python -m venv venv
venv\Scripts\activate
```

#### **On macOS/Linux**
```sh
python3 -m venv venv
source venv/bin/activate
```

---

### **3️⃣ Install Dependencies**
```sh
pip install -r requirements.txt
```

---

## **📌 Running the App**
```sh
streamlit run document-upload-parse.py
```
- After completing the upload step, run:
```sh
streamlit run dynamic-form-generation.py
```
- After filling out the form, the document will be generated.

---

## **📌 Required API Key**
This project uses **OpenAI API** for AI-powered text processing.  
Make sure you have an API key and set it in your environment:
```sh
export OPENAI_API_KEY="your-api-key"  # macOS/Linux
set OPENAI_API_KEY="your-api-key"  # Windows
```

---

## **🎯 Next Steps**
- Ensure your **template documents have placeholders formatted as `${placeholder_name}`**.
- AI-generated documents should **maintain original formatting**.
- Need enhancements? **Feel free to contribute!**
