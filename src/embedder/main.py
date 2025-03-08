import os
from llama_index.core.node_parser import TokenTextSplitter
import uuid
import pdfplumber
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import (
    Settings,
    Document,
    VectorStoreIndex,
    StorageContext,
)
from llama_index.vector_stores.postgres import PGVectorStore
from sqlalchemy import make_url, create_engine, text
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import tempfile
from minio import Minio
import traceback
import urllib.parse
from datetime import timedelta

logging.basicConfig(level=logging.INFO)

app = FastAPI()

postgres_conn_string = os.getenv(
    "POSTGRES_CONNECTION_STRING", 
    "postgresql://postgres:postgres@localhost:5432/rag-docs"
)

embed_model = HuggingFaceEmbedding(
    model_name="all-MiniLM-L6-v2"
)
Settings.embed_model = embed_model
Settings.chunk_size = 800
Settings.chunk_overlap = 50

text_splitter = TokenTextSplitter()

url = make_url(postgres_conn_string)
vector_store = PGVectorStore.from_params(
    database=url.database,
    host=url.host,
    password=url.password,
    port=url.port,
    user=url.username,
    embed_dim=384, 
)

storage_context = StorageContext.from_defaults(vector_store=vector_store)

minio_client = Minio(
    endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
    access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
    secure=False
)

def read_pdf(file_path):
    """Extract text from a PDF file using pdfplumber."""
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text()
    except Exception as e:
        logging.error(f"Error reading PDF {file_path}: {str(e)}")
        raise
    return text

def check_document_exists(filepath):
    """Check if documents with the given filepath already exist in the vector store."""
    try:
        engine = create_engine(postgres_conn_string)
        with engine.connect() as connection:
            query = text("""
                SELECT COUNT(*) 
                FROM data_llamaindex
                WHERE metadata_->>'filepath' = :filepath
            """)
            result = connection.execute(query, {"filepath": filepath}).scalar()
            return result > 0
    except Exception as e:
        logging.error(f"Error checking for existing document: {str(e)}")
        return False

def process_file(file_path, original_filename=None, original_filepath=None):
    """Process a file and store embeddings in PostgreSQL using LlamaIndex."""
    try:
        file_name = original_filename or os.path.basename(file_path)
        file_ext = os.path.splitext(file_name)[1].lower()
        
        filepath_to_check = original_filepath or file_path
        
        if check_document_exists(filepath_to_check):
            logging.info(f"File {file_name} ({filepath_to_check}) has already been processed. Skipping.")
            return {"status": "skipped", "reason": "already processed"}
            
        if file_ext == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        elif file_ext == '.pdf':
            content = read_pdf(file_path)
        else:
            logging.warning(f"Unsupported file type: {file_name}")
            return {"status": "skipped", "reason": "unsupported file type"}

        chunks = text_splitter.split_text(content)
        logging.info(f"Processing {file_name} - {len(chunks)} chunks created")

        documents = []
        for i, chunk in enumerate(chunks):
            try:
                metadata = {
                    "filename": file_name,
                    "filepath": original_filepath or file_path,
                    "chunk_id": i,
                    "doc_id": str(uuid.uuid4()),
                }
                
                doc = Document(
                    text=chunk,
                    metadata=metadata
                )
                documents.append(doc)
                
            except Exception as e:
                logging.error(f"Error creating document from chunk: {str(e)}")
                continue

        if documents:
            index = VectorStoreIndex.from_documents(
                documents,
                storage_context=storage_context
            )
            logging.info(f"Successfully indexed {len(documents)} documents from {file_name}")
        
        return {"status": "processed"}
        
    except Exception as e:
        logging.error(f"Error processing file {file_path}: {str(e)}")
        raise

@app.post('/minio-event')
async def handle_minio_event(request: Request):
    """Handle MinIO bucket notification events"""
    try:
        event_data = await request.json()
        logging.info(f"Received MinIO event: {event_data}")
        
        records = event_data.get('Records', [])
        if not records:
            return JSONResponse(
                content={"status": "error", "message": "No records in event"},
                status_code=400
            )
        
        results = []
        for record in records:
            s3_info = record.get('s3', {})
            bucket_name = s3_info.get('bucket', {}).get('name')
            object_key = s3_info.get('object', {}).get('key')
            event_name = record.get('eventName', '')
            
            if not (bucket_name and object_key):
                logging.error(f"Invalid event data: missing bucket or object info")
                continue
            
            if not event_name.startswith('s3:ObjectCreated:'):
                logging.info(f"Skipping event type: {event_name}")
                continue
            
            logging.info(f"Processing file {object_key} from bucket {bucket_name}")
            result = process_file_from_minio(bucket_name, object_key)
            results.append(result)
        
        return {
            "status": "success", 
            "message": f"Processed {len(results)} files",
            "results": results
        }
            
    except Exception as e:
        logging.error(f"Error processing MinIO event: {str(e)}")
        logging.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

def process_file_from_minio(bucket_name, object_key):
    """Download a file from MinIO and process it with the vectorizer"""
    try:
        decoded_object_key = urllib.parse.unquote(object_key)
        
        if not decoded_object_key.lower().endswith(('.txt', '.pdf')):
            logging.warning(f"Unsupported file type: {decoded_object_key}")
            return {"file": decoded_object_key, "status": "skipped", "reason": "unsupported file type"}
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(decoded_object_key)[1]) as temp_file:
            temp_path = temp_file.name
            
        logging.info(f"Downloading {decoded_object_key} from {bucket_name}")
        minio_client.fget_object(bucket_name, decoded_object_key, temp_path)
        
        minio_path = f"minio://{bucket_name}/{decoded_object_key}"
        
        logging.info(f"Processing {decoded_object_key}")
        result = process_file(temp_path, original_filename=decoded_object_key, original_filepath=minio_path)
        
        os.unlink(temp_path)
        
        response = {
            "file": decoded_object_key, 
            "bucket": bucket_name, 
            "status": result.get("status", "processed")
        }
            
        return response
        
    except Exception as e:
        logging.error(f"Error processing file {object_key} from bucket {bucket_name}: {str(e)}")
        logging.error(traceback.format_exc())
        return {
            "file": object_key, 
            "bucket": bucket_name, 
            "status": "error", 
            "error": str(e)
        }