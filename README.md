<p align="center">
<img src="assets/images/logo.png" height="250">
</p>
<h1 align="center">
RAG-DOCS
</h1>
<p align="center">
Chat with your documents using AI-powered search 
</p>
<p align="center">
<a href="https://github.com/daviaraujocc/rag-docs/blob/main/LICENSE"><img src="https://img.shields.io/github/license/daviaraujocc/rag-docs?color=blue" alt="License"></a>
<img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white" alt="Docker Ready">
<img src="https://img.shields.io/badge/Kubernetes-Ready-326CE5?logo=kubernetes&logoColor=white" alt="Kubernetes">
</p>

# Table of content

<details>
<summary>Expand contents</summary>

- [About](#about)
  - [Features](#features)
  - [Technology Stack](#technology-stack)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
  - [Requirements](#requirements)
  - [Installation](#installation)

</details>

## About

<div align="center">
<img src="assets/images/rag-docs.gif" alt="demo">
</div>

RAG-DOCS is a document search engine that uses RAG (Retrieval Augmented Generation) architecture to provide completions for your queries. The system allows users to upload documents, search for relevant information, and generate responses based on the retrieved context. 

### Features

- **Document Management**: Upload TXT and PDF files through a clean Gradio interface
- **Vector Search**: Intelligent document retrieval using pgvector similarity search
- **AI-powered Chat**: Interact with your documents using LLMs
- **Multiple LLM Options**: Use either local Ollama models or OpenAI API
- **Microservices Architecture**: Scalable design with separate components for each task
- **Containerized Deployment**: Ready for Docker and Kubernetes environments

### Technology Stack

<p align="center">
<img src="https://img.shields.io/badge/Gradio-FF6F00?logo=gradio&logoColor=white" alt="Gradio">
<img src="https://img.shields.io/badge/MinIO-C72E49?logo=minio&logoColor=white" alt="MinIO">
<img src="https://img.shields.io/badge/PostgreSQL-336791?logo=postgresql&logoColor=white" alt="PostgreSQL">
<img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI">
<img src="https://img.shields.io/badge/LlamaIndex-8A2BE2?logoColor=white" alt="LlamaIndex">
<img src="https://img.shields.io/badge/Ollama-000000?logoColor=white" alt="Ollama">
<img src="https://img.shields.io/badge/OpenAI-412991?logo=openai&logoColor=white" alt="OpenAI">
<img src="https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white" alt="Docker">
<img src="https://img.shields.io/badge/Kubernetes-326CE5?logo=kubernetes&logoColor=white" alt="Kubernetes">
<img src="https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/Helm-0F1689?logo=helm&logoColor=white" alt="Helm">
</p>

## Architecture

```mermaid
flowchart TD
    User([User]) <--> UI
    
    subgraph RAG_System
        UI[UI Service]
        Retriever[Retriever Service]
        Embedder[Embedder Service]
        Postgres[(fa:fa-database Postgres DB with pgvector)]
        MinIO[(fa:fa-hdd-o MinIO Storage)]
        CreateBuckets[CreateBuckets Setup Service]
        Ollama[fa:fa-robot Ollama LLM]
    end
    
    %% UI connections
    UI --> |Retrieves documents| Retriever
    UI --> |Accesses/Uploads files via S3| MinIO
    UI --> |Queries for completions| Ollama
    
    %% Retriever connections
    Retriever --> |Queries vector embeddings| Postgres
    
    %% Embedder connections
    Embedder --> |Stores vector embeddings| Postgres
    Embedder --> |Reads documents| MinIO
    
    %% MinIO connections
    MinIO -->|Webhook notification on upload| Embedder
    
    %% Setup
    CreateBuckets -->|Creates buckets and configures events| MinIO
    
    %% Enhanced color definitions
    classDef service fill:#9d4edd,stroke:#5a189a,stroke-width:2px,color:white
    classDef database fill:#48bfe3,stroke:#0077b6,stroke-width:2px,color:white
    classDef storage fill:#06d6a0,stroke:#087f5b,stroke-width:2px,color:white
    classDef external fill:#ff9e00,stroke:#ff7b00,stroke-width:3px
    classDef setup fill:#f72585,stroke:#7209b7,stroke-width:2px,color:white
    
    class UI,Retriever,Embedder service
    class Postgres database
    class MinIO storage
    class User external
    class CreateBuckets setup
    class Ollama service
```

### Communication Flow

1. **User Interaction**:
   - Users interact with the system through the UI service (Gradio)

2. **Document Processing**:
   - New documents are uploaded to MinIO storage
   - MinIO sends webhook notifications to the Embedder service
   - Embedder creates vector embeddings and stores them in the Postgres database

3. **Query Processing**:
   - UI sends queries to the Retriever service when chat is initiated
   - Retriever performs vector similarity search in Postgres
   - UI sends prompts to Ollama LLM along with retrieved context
   - Ollama returns generated responses to the UI

### Service Interfaces

| Service | Interface Port |
|---------|---------------|
| UI Service | 3000 |
| Retriever Service | 6000 |
| Embedder Service | 5000 |
| Postgres | 5432 |
| MinIO | 9000, 9001 |
| Ollama LLM | 11434 |


## Getting Started

### Requirements

- Docker

### Running

1. Clone the repository

```bash
git clone https://github.com/daviaraujocc/rag-docs && cd rag-docs
```

2. Start the system

```bash
docker-compose up -d --build
```

> Note: You need to setup the nvidia runtime for GPU support. Check the [official documentation](https://docs.docker.com/config/containers/resource_constraints/#access-an-nvidia-gpu) for more information.

3. Access the UI at [http://localhost:3000](http://localhost:3000)

#### OpenAI Option

If you prefer to use OpenAI instead of local Ollama models:

1. Edit docker-compose.openai.yaml and set your API key
2. Launch with:
   ```bash
   docker-compose -f docker-compose.openai.yaml up -d --build
   ```

### How to use

1. Upload a document (TXT or PDF)
2. Start a chat session
3. Ask questions and interact with the system

### 🚧 Kubernetes Deployment (WIP) 🚧

Deployment with helm charts soon.

### Environment Variables

Below are the environment variables for each service that can be modified to customize your deployment.

#### Embedder Service

| Variable | Description | Default Value |
|----------|-------------|---------------|
| `POSTGRES_CONNECTION_STRING` | PostgreSQL connection string | `postgresql://postgres:postgres@postgres:5432/rag-docs` |
| `MINIO_ENDPOINT` | MinIO server endpoint | `minio:9000` |
| `MINIO_ACCESS_KEY` | MinIO access key | `minioadmin` |
| `MINIO_SECRET_KEY` | MinIO secret key | `minioadmin` |
| `MINIO_SECURE` | Use HTTPS for MinIO connection | `false` |

#### Retriever Service

| Variable | Description | Default Value |
|----------|-------------|---------------|
| `POSTGRES_CONNECTION_STRING` | PostgreSQL connection string | `postgresql://postgres:postgres@postgres:5432/rag-docs` |
| `PORT` | Port for the Retriever service | `6000` |

#### UI Service

| Variable | Description | Default Value |
|----------|-------------|---------------|
| `RETRIEVER_API_URL` | URL for the Retriever service | `http://retriever:6000` |
| `S3_ENDPOINT` | MinIO server endpoint | `http://minio:9000` |
| `S3_PUBLIC_URL` | Public URL for accessing MinIO | `http://localhost:9000` |
| `S3_ACCESS_KEY` | MinIO access key | `minioadmin` |
| `S3_SECRET_KEY` | MinIO secret key | `minioadmin` |
| `SIMILARITY_THRESHOLD` | Threshold for similarity search | `0.25` |

##### Ollama Configuration (Default)

| Variable | Description | Default Value |
|----------|-------------|---------------|
| `LLM_PROVIDER` | LLM provider | `ollama` |
| `OLLAMA_BASE_URL` | Base URL for Ollama service | `http://ollama:11434` |
| `OLLAMA_MODEL` | Ollama model to use | `llama3.1:8b` |

##### OpenAI Configuration (Alternative)

| Variable | Description | Default Value |
|----------|-------------|---------------|
| `LLM_PROVIDER` | LLM provider | `openai` |
| `OPENAI_API_BASE` | OpenAI API base URL | `https://api.openai.com/v1/` |
| `OPENAI_API_KEY` | OpenAI API key | You must provide this |
| `OPENAI_MODEL` | OpenAI model to use | `gpt-3.5-turbo` |

#### PostgreSQL Service

| Variable | Description | Default Value |
|----------|-------------|---------------|
| `POSTGRES_USER` | PostgreSQL username | `postgres` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `postgres` |
| `POSTGRES_DB` | PostgreSQL database name | `rag-docs` |

#### MinIO Service

| Variable | Description | Default Value |
|----------|-------------|---------------|
| `MINIO_ROOT_USER` | MinIO root username | `minioadmin` |
| `MINIO_ROOT_PASSWORD` | MinIO root password | `minioadmin` |
| `MINIO_NOTIFY_WEBHOOK_ENABLE_EMBEDDER` | Enable webhook for Embedder | `on` |
| `MINIO_NOTIFY_WEBHOOK_ENDPOINT_EMBEDDER` | Webhook endpoint URL | `http://embedder:5000/minio-event` |

### Screenshots

<p align="center">
<img src="assets/images/ui-1.jpg">
<img src="assets/images/ui-2.jpg">
<img src="assets/images/ui-3.jpg">
</p>

### License

This project is available under the [MIT License](https://github.com/daviaraujocc/rag-docs/blob/main/LICENSE).


### TODO

- [ ] Add Helm charts for Kubernetes deployment
- [ ] Implement caching for faster responses
- [ ] Add support for more document formats
- [ ] Improve UI with more features
- [ ] Implement metrics and monitoring