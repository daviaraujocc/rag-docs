import os
import gradio as gr
import tempfile
import boto3
from botocore.client import Config
import logging
from llm import create_llm, check_ollama_model, download_ollama_model
import requests
import json
import mimetypes
import pandas as pd
from datetime import datetime
import re
import threading
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

llm_provider = config.LLM_PROVIDER
ollama_base_url = config.OLLAMA_BASE_URL
ollama_model = config.OLLAMA_MODEL

llm = None
model_download_in_progress = False

minio_client = boto3.client(
    's3',
    endpoint_url=config.S3_ENDPOINT,
    aws_access_key_id=config.S3_ACCESS_KEY,
    aws_secret_access_key=config.S3_SECRET_KEY
)

S3_PUBLIC_URL = config.S3_PUBLIC_URL
RETRIEVER_API_URL = config.RETRIEVER_API_URL
BUCKET_NAME = config.MINIO_BUCKET
SIMILARITY_THRESHOLD = config.SIMILARITY_THRESHOLD
PRESIGNED_URL_EXPIRATION = config.PRESIGNED_URL_EXPIRATION

try:
    if not minio_client.head_bucket(Bucket=BUCKET_NAME):
        minio_client.create_bucket(Bucket=BUCKET_NAME)
except Exception:
    minio_client.create_bucket(Bucket=BUCKET_NAME)

VIEWABLE_MIMETYPES = config.VIEWABLE_MIMETYPES

def get_presigned_url(filename):
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

        presigned_url = presigned_url.replace(config.S3_ENDPOINT, S3_PUBLIC_URL)
        
        return presigned_url, viewable
        
    except Exception as e:
        logger.error(f"Error generating presigned URL for {filename}: {str(e)}")
        return None, False

def upload_file(files):
    if not files:
        return "No files were uploaded."
    
    results = []
    
    with tempfile.TemporaryDirectory() as temp_dir:
        for file in files:
            try:
                file_path = file.name if hasattr(file, 'name') else str(file)
                file_name = os.path.basename(file_path)
                
                temp_path = os.path.join(temp_dir, file_name)
                
                if hasattr(file, 'read'):
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

def filter_files(search_term, df):
    if not search_term or df.empty or "Error" in df.columns:
        return df
    
    search_term = search_term.lower()
    
    filtered_df = df[
        df["Filename"].str.lower().str.contains(search_term, na=False) |
        df["Location"].str.lower().str.contains(search_term, na=False) |
        df["Type"].str.lower().str.contains(search_term, na=False)
    ]
    
    return filtered_df

model_download_status = "Not started"
model_download_percentage = 0

def check_model_availability():
    if llm_provider != "ollama":
        return True
    
    return check_ollama_model(ollama_base_url, ollama_model)

def get_model_status():
    global llm, model_download_in_progress, model_download_status, model_download_percentage
    
    if llm is None and check_model_availability():
        llm = create_llm()
        logger.info("LLM initialized")
    
    status = {
        "provider": llm_provider.capitalize(),
        "model": config.OPENAI_MODEL if llm_provider == "openai" else config.OLLAMA_MODEL,
        "download_in_progress": model_download_in_progress,
        "download_status": model_download_status,
        "download_percentage": model_download_percentage,
        "download_needed": False,
        "status": "Available" if llm is not None else "Available (not initialized)" 
    }
    
    if llm_provider == "openai":
        return status
    
    if llm is None and not check_model_availability():
        status.update({
            "status": "Not available",
            "download_needed": True
        })
    
    return status

def update_status(full_update=False):
    status = get_model_status()
    
    status_message = "## LLM Status\n\n"
    status_message += f"**Provider:** {status['provider']}\n\n"
    status_message += f"**Model:** {status['model']}\n\n"
    
    status_style = "green" if "Available" in status['status'] else "red"
    status_message += f"**Status:** <span style='color: {status_style}; font-weight: bold;'>{status['status']}</span>\n\n"
    
    if status['download_in_progress']:
        status_message += f"**Download Progress:** {status['download_percentage']}%\n\n"
        status_message += f"**Status:** {status['download_status']}\n\n"
    elif status['download_needed']:
        status_message += "**Download Status:** Required but not started. Click the 'Download Model' button below.\n\n"
    
    download_button_visibility = status['download_needed'] and not status['download_in_progress']
    
    if not full_update:
        return status_message, gr.update(visible=download_button_visibility)
    
    env_vars = get_environment_variables()
    
    return (
        status_message, 
        env_vars["LLM Configuration"],
        env_vars["Storage Configuration"],
        env_vars["Retriever Configuration"],
        gr.update(visible=download_button_visibility)
    )

def start_model_download():
    global llm, model_download_in_progress, model_download_status, model_download_percentage
    
    if model_download_in_progress:
        return "Download already in progress", False
        
    model_download_in_progress = True
    model_download_status = "Starting download..."
    model_download_percentage = 0
    
    def download_thread_func():
        global llm, model_download_in_progress, model_download_status, model_download_percentage
        try:
            status_messages = {
                "starting": "Initializing download...",
                "downloading": "Downloading: {progress}% complete",
                "completed": "Download complete!",
                "error": "Download failed!"
            }
            
            def progress_callback(progress_data):
                global model_download_percentage, model_download_status
                status = progress_data.get("status", "")
                progress = progress_data.get("progress", 0)
                model_download_percentage = progress
                
                message = status_messages.get(status, "")
                if status == "downloading":
                    message = message.format(progress=progress)
                if message:
                    model_download_status = message
            
            success, message = download_ollama_model(
                ollama_base_url, 
                ollama_model,
                progress_callback=progress_callback
            )
            
            if success:
                llm = create_llm()
                model_download_status = "Completed"
                model_download_percentage = 100
                logger.info(f"Model download completed: {message}")
            else:
                model_download_status = "Failed"
                logger.error(f"Model download failed: {message}")
        finally:
            model_download_in_progress = False
    
    download_thread = threading.Thread(target=download_thread_func)
    download_thread.daemon = True
    download_thread.start()
    
    return "Download started", False

def get_environment_variables():
    env_vars = config.get_env_vars_by_category()

    result = {}
    
    for category, variables in env_vars.items():
        category_content = []
        for key, value in variables.items():
            if "KEY" in key and value:
                masked_value = value[:4] + "*" * (len(value) - 8) + value[-4:] if len(value) > 8 else "***" 
                category_content.append(f"- **{key}**: {masked_value}")
            else:
                category_content.append(f"- **{key}**: {value}")
        
        result[category] = f"<details>\n<summary>## {category}</summary>\n\n" + "\n".join(category_content) + "\n</details>"

    return result

def chatbot_response(message, history):
    global llm, model_download_in_progress
    
    if llm is None:
        if not check_model_availability():
            return "⚠️ The required model is not available. Please go to the **System Settings** tab and click the **Download Model** button to download it before chatting."
        llm = create_llm()
    
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
        if llm is None:
            return "The system is still preparing the AI model. Please try again in a few minutes."
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
    
    .container-df {
        overflow-x: hidden !important; 
        overflow-y: auto !important;
    }
    .container-df > div {
        overflow-x: hidden !important;
        overflow-y: auto !important;
    }
    .container-df table {
        table-layout: fixed;
        width: 100%;
    }
    .container-df td {
        word-wrap: break-word;
        overflow-wrap: break-word;
        white-space: normal;
    }
    .container-df ::-webkit-scrollbar:horizontal {
        display: none;
    }
    
    .status-container {
        padding: 15px;
        border-radius: 10px;
    }
    .status-header {
        margin-bottom: 20px;
    }
    .model-status {
        font-size: 1.1em;
    }
    .download-progress {
        margin: 10px 0;
    }
    
    .download-button-container {
        text-align: left;
        margin-top: 10px;
        margin-bottom: 20px;
    }
    
    details {
        margin: 10px 0;
        padding: 10px;
        background-color: rgba(0,0,0,0.03);
        border-radius: 5px;
    }
    details summary {
        cursor: pointer;
        font-weight: bold;
        margin-bottom: 10px;
    }
    details summary h2 {
        display: inline;
        font-size: 1.3em;
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
                    return "", history + [[user_message, None]]
                
                def bot_response(history):
                    user_message = history[-1][0]
                    bot_message = chatbot_response(user_message, history[:-1])
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
                Upload documents to be indexed and made searchable. Supported formats include PDF and TXT.
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
                
                initial_df, initial_count = get_indexed_files()
                
                file_count = gr.Markdown(
                    f"**Total Files Indexed: {initial_count}**", 
                    elem_classes="file-stats"
                )
                
                with gr.Row(elem_classes="search-row"):
                    search_box = gr.Textbox(
                        label="Search Files",
                        placeholder="Type to search by filename, location, or type...",
                        show_label=False,
                        scale=9
                    )
                    clear_search_btn = gr.Button("✖ Clear", scale=1)
                
                files_table = gr.DataFrame(
                    value=initial_df,
                    interactive=False,
                    height=350,
                    wrap=True,
                    column_widths=["60%", "25%", "15%"],
                    elem_classes="container-df"
                )
                
                with gr.Row(elem_classes="refresh-btn"):
                    refresh_btn = gr.Button("🔄 Refresh List", variant="primary", size="sm")
                
                def update_files_display():
                    df, count = get_indexed_files()
                    return df, f"**Total Files Indexed: {count}**", ""
                
                def search_files(search_term):
                    df, _ = get_indexed_files()
                    filtered_df = filter_files(search_term, df)
                    return filtered_df
                
                def clear_search():
                    df, _ = get_indexed_files()
                    return df, ""
                
                refresh_btn.click(
                    update_files_display,
                    inputs=None,
                    outputs=[files_table, file_count, search_box]
                )
                
                search_box.change(
                    search_files,
                    inputs=search_box,
                    outputs=files_table
                )
                
                clear_search_btn.click(
                    clear_search,
                    inputs=None,
                    outputs=[files_table, search_box]
                )
            
            with gr.TabItem("System Settings", elem_classes="status-container", visible=True): 
                with gr.Column(elem_classes="status-header"):
                    gr.Markdown("## System Settings")
            
                
                with gr.Column(elem_classes="status-section"):
                    model_status_text = gr.Markdown("Loading status...", elem_classes="model-status")
                    
                    with gr.Row(elem_classes="download-button-container"):
                        download_btn = gr.Button("⬇️ Download Model", variant="primary", size="sm", visible=False, scale=0)
                        refresh_status_btn = gr.Button("🔄 Refresh Status", variant="primary", size="sm", scale=0)
                        gr.Column(scale=1)
                       

                gr.Markdown("---")
                
                with gr.Column(elem_classes="config-section"):
                    llm_config_text = gr.Markdown("", elem_classes="llm-config")
                    
                    storage_config_text = gr.Markdown("", elem_classes="storage-config")
                    
                    retriever_config_text = gr.Markdown("", elem_classes="retriever-config")
                
                gr.Markdown("---")

                refresh_status_btn.click(
                    lambda: update_status(False),
                    inputs=[],
                    outputs=[
                        model_status_text,
                        download_btn
                    ]
                )
                
                download_btn.click(
                    start_model_download,
                    inputs=[],
                    outputs=[model_status_text, download_btn]
                ).then(
                    lambda: update_status(True),
                    inputs=[],
                    outputs=[
                        model_status_text,
                        llm_config_text,
                        storage_config_text,
                        retriever_config_text,
                        download_btn
                    ]
                )
                
                app.load(
                    lambda: update_status(True),
                    inputs=[],
                    outputs=[
                        model_status_text,
                        llm_config_text,
                        storage_config_text,
                        retriever_config_text,
                        download_btn
                    ]
                )

if __name__ == "__main__":
    app.launch(server_name=config.SERVER_HOST, server_port=config.SERVER_PORT)
