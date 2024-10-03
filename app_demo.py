import streamlit as st
from openai import OpenAI
import os
import re
from datetime import datetime
import pathlib
from llama_parse import LlamaParse
from tqdm import tqdm


# Add secret key input
st.sidebar.title("o1-mini With File and Image Capabilities")
st.sidebar.markdown("This is the online demo and does not collect any user data")
# secret_key_input = st.sidebar.text_input("Secret Key", type='password')

# Validate secret key and retrieve API keys from environment variables
# if not secret_key_input:
#     st.sidebar.info("Please input passcode.")
#     st.stop()
# elif secret_key_input == "ABC123":
#     openai_api_key = os.getenv("OPENAI_API_KEY")
#     anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
#     llama_parse_api_key = os.getenv("LLAMA_PARSE_API_KEY")
# else:
#     st.sidebar.error("Invalid Secret Key.")
#     st.stop()

# # comment out when adding secret key
openai_api_key = os.getenv("OPENAI_API_KEY")
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
llama_parse_api_key = os.getenv("LLAMA_PARSE_API_KEY")

# Initialize OpenAI client with user-provided API key
client = OpenAI(api_key=openai_api_key)

def generate_response(prompt, model):
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    return response.choices[0].message.content

def summarize_inquiry(prompt):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Summarize the following inquiry into a short phrase suitable for a filename (less than 10 words, use underscores between words, only use alphanumeric characters and underscores)."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=15
    )
    summary_filename = response.choices[0].message.content.strip()
    
    # Post-process the summary to ensure it's filename-friendly, as gpt-4o-mini may not always output a clean filename
    summary_filename = re.sub(r'[^a-zA-Z0-9_]', '_', summary_filename)  # Replace non-alphanumeric chars with underscore
    summary_filename = re.sub(r'_+', '_', summary_filename)  # Replace multiple underscores with single underscore
    summary_filename = summary_filename.strip('_')  # Remove leading/trailing underscores
    
    return summary_filename

def replace_latex_delimiters(text):
    # Replace inline math delimiters \(...\) with \[...\]
    text = re.sub(r'\\\((.*?)\\\)', r'\\[\1\\]', text, flags=re.DOTALL)
    # Replace display math delimiters \[...\] with $$...$$
    text = re.sub(r'\\\[(.*?)\\\]', r'$$\1$$', text, flags=re.DOTALL)
    return text

def save_markdown(prompt, response):
    
    # Generate filename
    now = datetime.now()
    date_time = now.strftime("%Y-%m-%d-%H%M%S")
    summary_filename = summarize_inquiry(prompt)
    filename = f"Response/{date_time}-{summary_filename}.md"
    
    # **Store the timestamp in session state**
    st.session_state.date_time = date_time

    # Create markdown content
    markdown_content = f"# Question\n\n{prompt}\n\n---\n\n# Response\n\n{response}"
    
    # Save to file
    with open(filename, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    
    return filename

st.title("OpenAI o1-mini Augmented with File & Image Handling Capabilities")
st.info("We developed this exciting free app to enhance OpenAI o1 with file and image capabilities, which is not natively supported yet. Try with your short PDFs, documents, or images!")
st.info("Update on Sep 25, 2024: v0.2 released. See side bar for update log.")

model = st.radio("Select Model", ["o1-mini"], index=0)
with_formula = st.toggle("With Formula (Turn on when solving math problems)", value=False, help="Render formula in LaTeX")
multimodal_parse = st.toggle("Multimodal Parse (Turn on only when dealing with images)", value=False, help="Use multimodal parsing (anthropic-sonnet-3.5) for uploaded files")

# Update the file uploader to accept multiple files
uploaded_files = st.file_uploader("Upload files (optional, up to 2) [Note: **Avoid excessively long PDFs or large files**]", type=[
    "pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx",
    "txt", "rtf", "csv", "htm", "html",
    "jpg", "jpeg", "png", "gif", "bmp", "svg", "tiff", "webp",
    "odt", "ods", "odp", "epub"
], accept_multiple_files=True)

# Use a form to capture user input
with st.form(key='prompt_form'):
    user_input = st.text_area("Enter your prompt (Ctrl+Enter to submit):", height=100, key="prompt")
    submit_button = st.form_submit_button(label='Generate Response', use_container_width=True)

# Append "include all formula in latex" if the toggle is on
if with_formula:
    user_input += " ,produce formula in latex, but keep table in markdown format"

# Check if Ctrl+Enter was pressed
if st.session_state.prompt and st.session_state.prompt.endswith('\n'):
    submit_button = True

if submit_button:
    if user_input or uploaded_files:
        # Show warning message
        warning_placeholder = st.empty()
        warning_placeholder.warning("Parsing and generating response, please do not reclick. Long PDFs / large files may take more time.")
        
        # Process uploaded files if present
        if uploaded_files:
            if len(uploaded_files) > 2:
                st.error("Please upload a maximum of 2 files.")
            else:
                if not llama_parse_api_key:
                    st.error("Please enter your Llama Parse API key.")
                elif multimodal_parse and not anthropic_api_key:
                    st.error("Please enter your Anthropic API key for multimodal parsing.")
                else:
                    try:
                        # parsing_instruction = f"Pay special attention to user's question on {user_input} and append the answer to parsed output."
                        # Initialize LlamaParse
                        parser_args = {
                            "api_key": llama_parse_api_key,
                            "result_type": "markdown",
                            "verbose": True,
                            "language": "en",
                            "num_workers": 9,
                            #"parsing_instruction": parsing_instruction,
                        }

                        # Check if any uploaded file is an image
                        image_extensions = ["jpg", "jpeg", "png", "gif", "bmp", "svg", "tiff", "webp"]
                        if any(uploaded_file.name.split('.')[-1].lower() in image_extensions for uploaded_file in uploaded_files):
                            multimodal_parse = True
                        st.write(f"Multimodal Parse: {'Auto-Enabled Due to Image Upload' if multimodal_parse else 'Disabled, turn on if error with parsed content'}")

                        if multimodal_parse:
                            parser_args["use_vendor_multimodal_model"] = True
                            parser_args["vendor_multimodal_model_name"] = "anthropic-sonnet-3.5"
                            parser_args["vendor_multimodal_api_key"] = anthropic_api_key
                        
                        parser = LlamaParse(**parser_args)
                        
                        all_extracted_text = []
                        
                        # Create a progress bar
                        progress_bar = st.progress(0)
                        total_files = len(uploaded_files)
                        
                        for i, uploaded_file in enumerate(uploaded_files, 1): 
                            # Read file content
                            file_content = uploaded_file.read()
                            
                            # Parse file content
                            documents = parser.load_data(file_content, extra_info={"file_name": uploaded_file.name})
                            
                            # Combine all documents into one markdown string
                            extracted_text = f"# File {i}: {uploaded_file.name}\n\n" + "\n\n".join([doc.text for doc in documents])
                            all_extracted_text.append(extracted_text)

                            if i > 0:  # Only update progress after the first file is parsed
                                progress = i / total_files
                                progress_bar.progress(progress)
                        
                        # Combine all extracted text
                        combined_extracted_text = "\n\n".join(all_extracted_text)
                        
                        st.markdown("### Extracted Text from Files:")
                        st.text_area("Extracted Text", combined_extracted_text, height=200)
                        user_input = f"{user_input}\n\nFile content:\n{combined_extracted_text}"
                    except Exception as e:
                        st.error(f"An error occurred while processing the files: {str(e)}")
                        st.warning("No text was extracted from the files. They might be empty or unreadable.")
        
        with st.spinner("Generating response..."):
            response = generate_response(user_input, model)
        
        # Remove the warning message
        warning_placeholder.empty()
        
        # Display raw response
        st.subheader("Raw Generated Response:")
        st.text_area("Raw response", value=response, height=200, label_visibility="collapsed")
        
        # Process and display response with LaTeX rendering
        processed_response = replace_latex_delimiters(response)
        st.subheader("Response:")
        st.markdown(processed_response)
        
        # Save markdown file
        markdown_file = save_markdown(user_input, processed_response)
        # st.success(f"Response saved to {markdown_file}")
        
        # Provide download link
        with open(markdown_file, "r", encoding="utf-8") as f:
            st.download_button(
                label="Download Prompt and Answer",
                data=f.read(),
                file_name=os.path.basename(markdown_file),
                mime="text/markdown"
            )

    else:
        st.warning("Please enter a prompt or upload an image.")

st.markdown("---")

st.sidebar.header("Github Link")
st.sidebar.markdown("**[Github Link](https://github.com/liyimengwork/o1-with-file-and-image-capabilities-public)**")

st.sidebar.header("Update Log")
st.sidebar.markdown("**Sep 25, 2024 - v0.2**: Support for multiple file uploads (up to 2). Fixed known issues with parsing.")
st.sidebar.markdown("**Sep 23, 2024 - v0.1**: Initial version released.")