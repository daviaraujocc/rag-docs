import os
import gradio as gr
import tempfile
import boto3
from botocore.client import Config
import logging
from llm import create_llm
import requests
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize LLM client for response generation
llm = create_llm(
    provider="ollama",
    model="llama3.1:8b",
)

# Initialize MinIO client
minio_client = boto3.client(
    's3',
    endpoint_url=os.getenv("MINIO_ENDPOINT", "http://localhost:9000"),
    aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
    aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
    config=Config(signature_version='s3v4'),
    region_name='us-east-1'
)

# API endpoint configuration
RETRIEVER_API_URL = os.getenv("RETRIEVER_API_URL", "http://localhost:5001")
BUCKET_NAME = os.getenv("MINIO_BUCKET", "documents")
SIMILARITY_THRESHOLD = os.getenv("SIMILARITY_THRESHOLD", 0.25)

# Ensure the bucket exists
try:
    if not minio_client.head_bucket(Bucket=BUCKET_NAME):
        minio_client.create_bucket(Bucket=BUCKET_NAME)
except Exception:
    minio_client.create_bucket(Bucket=BUCKET_NAME)

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
                    filename_entry = f"- {result['filename']}"
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
    .container { max-width: 850px; margin: auto; }
    .title-container { text-align: center; margin-bottom: 20px; }
    .title-container h1 { color: #3498db; }
    footer { display: none !important; }
    .chat-container { border-radius: 10px; }
    .upload-container { border-radius: 10px; padding: 15px; }
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

# Launch the app
if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=3000)
