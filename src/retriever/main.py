from flask import Flask, request, jsonify
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import (
    Settings,
    VectorStoreIndex,
)
from llama_index.vector_stores.postgres import PGVectorStore
from sqlalchemy import make_url
import os
import logging

app = Flask(__name__)

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
    embed_model=embed_model
)

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

@app.route('/search', methods=['GET'])
def search_handler():
    try:
        query = request.args.get('query', '')
        top_k = int(request.args.get('top_k', '5'))
        
        if not query:
            return jsonify({"error": "Missing query parameter"}), 400
        
        search_results = semantic_search(query, top_k)
        
        return jsonify({
            "results": search_results
        })
        
    except Exception as e:
        logging.error(f"Search error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5001))
    app.run(host=host, port=port, debug=os.getenv("DEBUG", "false").lower() == "true")