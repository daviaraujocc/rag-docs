import os

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Storage Configuration
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
S3_PUBLIC_URL = os.getenv("S3_PUBLIC_URL", "http://localhost:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "documents")

# Retriever Configuration
RETRIEVER_API_URL = os.getenv("RETRIEVER_API_URL", "http://localhost:5001")
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", 0.25))
PRESIGNED_URL_EXPIRATION = int(os.getenv("PRESIGNED_URL_EXPIRATION", 3600))

# UI Configuration
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", 3000))


VIEWABLE_MIMETYPES = [
    'text/plain', 'text/html', 'text/css', 'text/javascript',
    'application/pdf', 'image/jpeg', 'image/png', 'image/gif',
    'image/svg+xml'
]

def get_env_vars_by_category():
    """Return environment variables organized by category for UI display"""
    return {
        "LLM Configuration": {
            "LLM_PROVIDER": LLM_PROVIDER,
            "OLLAMA_BASE_URL": OLLAMA_BASE_URL,
            "OLLAMA_MODEL": OLLAMA_MODEL,
            "OPENAI_API_BASE": OPENAI_API_BASE,
            "OPENAI_MODEL": OPENAI_MODEL,
        },
        "Storage Configuration": {
            "S3_ENDPOINT": S3_ENDPOINT,
            "S3_PUBLIC_URL": S3_PUBLIC_URL,
            "MINIO_BUCKET": MINIO_BUCKET,
        },
        "Retriever Configuration": {
            "RETRIEVER_API_URL": RETRIEVER_API_URL,
            "SIMILARITY_THRESHOLD": SIMILARITY_THRESHOLD,
            "PRESIGNED_URL_EXPIRATION": PRESIGNED_URL_EXPIRATION,
        }
    }
