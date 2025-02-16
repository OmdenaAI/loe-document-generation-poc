# loe-document-generation-poc
Create a `.env` file with the following variables:
`OPENAI_API_KEY=[your-api-key]`

To run the script:
1- Run `document-uploader.py` to upload the document to extract placeholders and download the template.json file.
2- Run `dynamic-form-generator.py` which will load the template.json file(it should be in the root directory) and generate a dynamic form using Streamlit, then download the final document.
