from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import (
    Settings,
    VectorStoreIndex,
)
from llama_index.vector_stores.postgres import PGVectorStore
from sqlalchemy import make_url, create_engine, text
import os
import logging

app = FastAPI()

logging.basicConfig(level=logging.INFO)

postgres_conn_string = os.getenv(
    "POSTGRES_CONNECTION_STRING", 
    "postgresql://postgres:postgres@localhost:5432/rag-docs"
)

embed_model = HuggingFaceEmbedding(
    model_name="all-MiniLM-L6-v2"
)

Settings.embed_model = embed_model

url = make_url(postgres_conn_string)
vector_store = PGVectorStore.from_params(
    database=url.database,
    host=url.host,
    password=url.password,
    port=url.port,
    user=url.username,
    embed_dim=384, 
)

index = VectorStoreIndex.from_vector_store(
    vector_store,
)

def get_all_indexed_files():
    """Retrieve all unique files from the vector store's metadata_"""
    try:
        engine = create_engine(postgres_conn_string)
        with engine.connect() as connection:
            query = text("""
                SELECT DISTINCT 
                    metadata_->>'filename' as filename, 
                    metadata_->>'filepath' as filepath 
                FROM data_llamaindex
                WHERE metadata_->>'filename' IS NOT NULL
                ORDER BY metadata_->>'filename'
            """)
            result = connection.execute(query)
            files = [{"filename": row[0], "filepath": row[1]} for row in result]
            return files
    except Exception as e:
        logging.error(f"Error fetching indexed files: {str(e)}")
        return []

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

def semantic_search(query, top_k=5):
    """Perform semantic search using the vector store directly or through the index"""
    retriever = index.as_retriever(similarity_top_k=top_k)
    nodes = retriever.retrieve(query)
    
    return [
        {
            "content": node.text,
            "similarity_score": node.score if hasattr(node, "score") else 0.0,
            "filename": node.metadata.get("filename", ""),
            "filepath": node.metadata.get("filepath", "")
        }
        for node in nodes
    ]

class FilesResponse(BaseModel):
    files: List[Dict[str, str]]
    count: int

class SearchResult(BaseModel):
    content: str
    similarity_score: float
    filename: str
    filepath: str

class SearchResponse(BaseModel):
    results: List[SearchResult]

@app.get('/files', response_model=FilesResponse)
def list_files_handler():
    try:
        files = get_all_indexed_files()
        return {"files": files, "count": len(files)}
    except Exception as e:
        logging.error(f"Files listing error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get('/search', response_model=SearchResponse)
def search_handler(query: str = Query(..., description="Search query"), 
                   top_k: int = Query(5, description="Number of results to return")):
    try:
        if not query:
            raise HTTPException(status_code=400, detail="Missing query parameter")
        
        search_results = semantic_search(query, top_k)
        
        return {"results": search_results}
        
    except Exception as e:
        logging.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
@app.get('/health', response_class=JSONResponse)
def health_check():
    return JSONResponse(content={"status": "ok"})