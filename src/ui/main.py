import os
import gradio as gr
import tempfile
import boto3
from botocore.client import Config
import logging
from llm import create_llm
import requests
import json
import mimetypes
import pandas as pd
from datetime import datetime
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize LLM client for response generation
llm = create_llm()

# Initialize MinIO client
minio_client = boto3.client(
    's3',
    endpoint_url=os.getenv("S3_ENDPOINT", "http://localhost:9000"),
    aws_access_key_id=os.getenv("S3_ACCESS_KEY", "minioadmin"),
    aws_secret_access_key=os.getenv("S3_SECRET_KEY", "minioadmin")
)

S3_PUBLIC_URL = os.getenv("S3_PUBLIC_URL", "http://localhost:9000")
RETRIEVER_API_URL = os.getenv("RETRIEVER_API_URL", "http://localhost:5001")
BUCKET_NAME = os.getenv("MINIO_BUCKET", "documents")
SIMILARITY_THRESHOLD = os.getenv("SIMILARITY_THRESHOLD", 0.25)
PRESIGNED_URL_EXPIRATION = int(os.getenv("PRESIGNED_URL_EXPIRATION", 3600))  # 1 hour default

try:
    if not minio_client.head_bucket(Bucket=BUCKET_NAME):
        minio_client.create_bucket(Bucket=BUCKET_NAME)
except Exception:
    minio_client.create_bucket(Bucket=BUCKET_NAME)

VIEWABLE_MIMETYPES = [
    'text/plain', 'text/html', 'text/css', 'text/javascript',
    'application/pdf', 'image/jpeg', 'image/png', 'image/gif',
    'image/svg+xml'
]

def get_presigned_url(filename):
    """
    Generate a presigned URL for accessing a document in MinIO,
    configured for browser viewing when possible
    """
    try:
        content_type, _ = mimetypes.guess_type(filename)
        if not content_type:
            content_type = 'application/octet-stream'
        
        viewable = content_type in VIEWABLE_MIMETYPES
        
        response_headers = {
            'ResponseContentType': content_type
        }
        
        if not viewable:
            response_headers['ResponseContentDisposition'] = f'attachment; filename="{filename}"'
        
        presigned_url = minio_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': filename,
                **response_headers
            },
            ExpiresIn=PRESIGNED_URL_EXPIRATION
        )

        presigned_url = presigned_url.replace(os.getenv("S3_ENDPOINT", "http://localhost:9000"), S3_PUBLIC_URL)
        
        return presigned_url, viewable
        
    except Exception as e:
        logger.error(f"Error generating presigned URL for {filename}: {str(e)}")
        return None, False

def upload_file(files):
    """Handle file upload to MinIO but let retriever API handle indexing later"""
    if not files:
        return "No files were uploaded."
    
    results = []
    
    with tempfile.TemporaryDirectory() as temp_dir:
        for file in files:
            try:
                file_path = file.name if hasattr(file, 'name') else str(file)
                file_name = os.path.basename(file_path)
                
                temp_path = os.path.join(temp_dir, file_name)
                
                if hasattr(file, 'read'):  # File-like object
                    with open(temp_path, 'wb') as f:
                        content = file.read()
                        if isinstance(content, str):
                            content = content.encode('utf-8')
                        f.write(content)
                else:  
                    with open(file, 'rb') as src, open(temp_path, 'wb') as dst:
                        dst.write(src.read())
                
                with open(temp_path, 'rb') as f:
                    minio_client.upload_fileobj(
                        f, 
                        BUCKET_NAME, 
                        file_name
                    )
                
                results.append(f"✓ Uploaded file: {file_name}")
                    
            except Exception as e:
                logger.error(f"Error uploading file {file_path if 'file_path' in locals() else 'unknown'}: {str(e)}")
                results.append(f"✗ Error uploading file: {str(e)}")
    
    return "\n".join(results)

def get_indexed_files():
    """
    Fetch the list of indexed files from the retriever API and format for display
    """
    try:
        response = requests.get(f"{RETRIEVER_API_URL}/files")
        
        if response.status_code == 200:
            api_response = response.json()
            files_list = api_response.get("files", [])
            files_count = api_response.get("count", 0)
            
            if files_list:
                data = {
                    "Filename": [],
                    "Location": [],
                    "Type": []
                }
                
                for file in files_list:
                    filename = file['filename']
                    filepath = file['filepath']
                    
                    ext = os.path.splitext(filename)[1].lstrip('.').upper()
                    if not ext:
                        ext = "Unknown"
                    
                    data["Filename"].append(filename)
                    data["Location"].append(filepath)
                    data["Type"].append(ext)
                
                df = pd.DataFrame(data)
                return df, files_count
            else:
                df = pd.DataFrame({
                    "Filename": [],
                    "Location": [],
                    "Type": []
                })
                return df, 0
        else:
            logger.warning(f"Failed to get indexed files (status {response.status_code}).")
            df = pd.DataFrame({
                "Error": [f"Could not retrieve indexed files (status {response.status_code})."]
            })
            return df, 0
            
    except Exception as e:
        logger.error(f"Error calling retriever API: {str(e)}")
        df = pd.DataFrame({
            "Error": [f"Could not connect to retrieval service: {str(e)}"]
        })
        return df, 0

# Add a new function to filter files based on search term
def filter_files(search_term, df):
    """Filter the files DataFrame based on search term"""
    if not search_term or df.empty or "Error" in df.columns:
        return df
    
    search_term = search_term.lower()
    
    filtered_df = df[
        df["Filename"].str.lower().str.contains(search_term, na=False) |
        df["Location"].str.lower().str.contains(search_term, na=False) |
        df["Type"].str.lower().str.contains(search_term, na=False)
    ]
    
    return filtered_df

def chatbot_response(message, history):
    """
    Get contexts from retriever API but generate response locally
    Properly formatted for Gradio chatbot
    """
    try:
        response = requests.get(
            f"{RETRIEVER_API_URL}/search",
            params={"query": message, "top_k": 5}
        )
        
        if response.status_code == 200:
            api_response = response.json()
            search_results = api_response.get("results", [])
            
            context = ""
            sources = []
            
            for result in search_results:
                if "content" in result and float(result["similarity_score"]) < float(SIMILARITY_THRESHOLD):
                    continue
                if "content" in result and result["content"]:
                    context += result["content"] + "\n\n"
                if "filename" in result and result["filename"]:
                    filename = result['filename']
                    
                    # Generate presigned URL for this document
                    presigned_url, viewable = get_presigned_url(filename)
                    
                    if presigned_url:
                        view_text = "View in browser" if viewable else "Download"
                        filename_entry = f"- [{filename}]({presigned_url}) ({view_text})"
                    else:
                        filename_entry = f"- {filename}"
                        
                    if filename_entry not in sources:
                        sources.append(filename_entry)
            
            if context:
                prompt = f"""Instruction: Answer the question based on the context below.
                If you don't know the answer based on the context, say "I don't have enough information to answer this question."
                
                Context: {context}
                
                Question: {message}
                
                Answer:"""
                
                response = llm.complete(prompt).text
                
                if sources:
                    response = response + "\n\nSources:\n" + "\n".join(sources)
                
                return response
            else:
                direct_response = "Sorry, i don't have enough information to answer this question."
                return f"{direct_response}\n\n(Note: No relevant documents were found, try rephrasing your question.)"
                
        else:
            logger.warning(f"API unavailable (status {response.status_code}). Using direct LLM fallback.")
            direct_response = llm.complete(f"Question: {message}\n\nAnswer:").text
            return f"{direct_response}\n\n(Note: This response was generated without document context as the retrieval service is unavailable.)"
            
    except Exception as e:
        logger.error(f"Error calling retriever API: {str(e)}")
        direct_response = llm.complete(f"Question: {message}\n\nAnswer:").text
        return f"{direct_response}\n\n(Note: This response was generated without document context as the retrieval service is unavailable.)"

js_func = """
function refresh() {
    const url = new URL(window.location);

    if (url.searchParams.get('__theme') !== 'dark') {
        url.searchParams.set('__theme', 'dark');
        window.location.href = url.href;
    }
}
"""

# Create Gradio interface
with gr.Blocks(title="RAG Docs Assistant", js=js_func, theme="soft", css="""
    .container { max-width: 1200px; margin: auto; }
    .title-container { text-align: center; margin-bottom: 20px; }
    .title-container h1 { color: #3498db; }
    footer { display: none !important; }
    .chat-container { border-radius: 10px; }
    .upload-container { border-radius: 10px; padding: 15px; }
    .files-container { border-radius: 10px; padding: 15px; }
    .file-stats { text-align: center; font-size: 1.2em; margin-bottom: 15px; }
    .search-row { margin-bottom: 15px; }
    .refresh-btn { text-align: center; margin-top: 10px; }
    table { width: 100%; border-collapse: collapse; }
    th { background-color: #3498db; color: white; text-align: left; padding: 10px; }
    td { padding: 8px; border-bottom: 1px solid #ddd; }
    
    /* Enhanced table layout and scroll control */
    .container-df {
        overflow-x: hidden !important; 
        overflow-y: auto !important;
    }
    .container-df > div {
        overflow-x: hidden !important;
        overflow-y: auto !important;
    }
    /* Fixed layout to prevent horizontal expansion */
    .container-df table {
        table-layout: fixed;
        width: 100%;
    }
    /* Ensure text wraps inside cells */
    .container-df td {
        word-wrap: break-word;
        overflow-wrap: break-word;
        white-space: normal;
    }
    /* Hide horizontal scrollbar in all nested elements */
    .container-df ::-webkit-scrollbar:horizontal {
        display: none;
    }
""") as app:
    with gr.Column(elem_classes="container"):
        with gr.Column(elem_classes="title-container"):
            gr.Markdown("# RAG Documents Assistant")
            gr.Markdown("_Chat with your documents using AI-powered search_")
        
        with gr.Tabs():
            with gr.TabItem("Chat", elem_classes="chat-container"):
                gr.Markdown("""
                ## Chat with your documents
                Ask questions about your uploaded documents. The assistant will retrieve relevant information before responding.
                """)
                
                chatbot = gr.Chatbot(height=500, elem_classes="chatbox")
                
                with gr.Row():
                    msg = gr.Textbox(
                        label="Your question", 
                        placeholder="Ask something about your documents...",
                        scale=9
                    )
                    send_btn = gr.Button("Send", variant="primary", scale=1)
                
                clear = gr.Button("Clear Chat", variant="secondary")
                
                def user_input(user_message, history):
                    # Append user message to history
                    return "", history + [[user_message, None]]
                
                def bot_response(history):
                    # Get the last user message
                    user_message = history[-1][0]
                    # Get response from chatbot
                    bot_message = chatbot_response(user_message, history[:-1])
                    # Update history
                    history[-1][1] = bot_message
                    return history
                
                msg.submit(
                    user_input,
                    [msg, chatbot],
                    [msg, chatbot],
                    queue=False
                ).then(
                    bot_response,
                    [chatbot],
                    [chatbot]
                )
                
                # Connect the send button to the same flow
                send_btn.click(
                    user_input,
                    [msg, chatbot],
                    [msg, chatbot],
                    queue=False
                ).then(
                    bot_response,
                    [chatbot],
                    [chatbot]
                )
                
                clear.click(lambda: None, None, chatbot, queue=False)
                    
            with gr.TabItem("Upload Documents", elem_classes="upload-container"):
                gr.Markdown("""
                ## Upload Documents
                Upload documents to be indexed and made searchable. Supported formats include PDF, DOCX, and images.
                """)
                
                upload_input = gr.Files(label="Upload Files", file_count="multiple")
                upload_button = gr.Button("Upload and Process", variant="primary")
                upload_output = gr.Textbox(label="Upload Status", interactive=False)
                
                upload_button.click(
                    upload_file,
                    inputs=upload_input,
                    outputs=upload_output
                )
                
            with gr.TabItem("Indexed Files", elem_classes="files-container"):
                gr.Markdown("""
                ## Indexed Files
                View the list of files that have been indexed and are available for searching.
                """)
                
                # Get initial data
                initial_df, initial_count = get_indexed_files()
                
                # Display file count
                file_count = gr.Markdown(
                    f"**Total Files Indexed: {initial_count}**", 
                    elem_classes="file-stats"
                )
                
                # Modified search functionality (removed search button)
                with gr.Row(elem_classes="search-row"):
                    search_box = gr.Textbox(
                        label="Search Files",
                        placeholder="Type to search by filename, location, or type...",
                        show_label=False,
                        scale=9  # Adjusted scale to take more space
                    )
                    clear_search_btn = gr.Button("✖ Clear", scale=1)
                
                # Display files in a DataFrame with improved styling
                files_table = gr.DataFrame(
                    value=initial_df,
                    interactive=False,
                    height=350,
                    wrap=True,
                    column_widths=["60%", "25%", "15%"],
                    elem_classes="container-df"  # Added class for CSS targeting
                )
                
                with gr.Row(elem_classes="refresh-btn"):
                    refresh_btn = gr.Button("🔄 Refresh List", variant="primary", size="sm")
                
                def update_files_display():
                    df, count = get_indexed_files()
                    return df, f"**Total Files Indexed: {count}**", ""  # Clear search box
                
                def search_files(search_term):
                    df, _ = get_indexed_files()
                    filtered_df = filter_files(search_term, df)
                    return filtered_df
                
                def clear_search():
                    df, _ = get_indexed_files()
                    return df, ""  # Return full list and clear search box
                
                # Connect refresh button
                refresh_btn.click(
                    update_files_display,
                    inputs=None,
                    outputs=[files_table, file_count, search_box]
                )
                
                # Remove search button connection, keep only the search box change event
                search_box.change(
                    search_files,
                    inputs=search_box,
                    outputs=files_table
                )
                
                # Connect clear search button
                clear_search_btn.click(
                    clear_search,
                    inputs=None,
                    outputs=[files_table, search_box]
                )

# Launch the app
if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=3000)
