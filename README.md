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
<img src="https://img.shields.io/badge/License-MIT-green" alt="License"></a>
<img src="https://img.shields.io/github/v/tag/daviaraujocc/rag-docs">
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
  - [Hardware requirements](#hardware-requirements)
   - [Pre-requisites](#pre-requisites)
   - [Running](#running)
   - [Using OpenAI as an Alternative](#using-openai-as-an-alternative)
- [Interacting with RAG-DOCS](#interacting-with-rag-docs)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Environment Variables](#environment-variables)
  - [Embedder Service](#embedder-service)
  - [Retriever Service](#retriever-service)
  - [UI Service](#ui-service)
  - [Ollama Configuration (Default)](#ollama-configuration-default)
  - [OpenAI Configuration (Alternative)](#openai-configuration-alternative)
  - [PostgreSQL Service](#postgresql-service)
  - [MinIO Service](#minio-service)
- [Service Interfaces](#service-interfaces)
- [Screenshots](#screenshots)
- [Troubleshooting and FAQs](#troubleshooting-and-faqs)
- [License](#license)

</details>

## About

<div align="center">
<img src="assets/images/rag-docs.gif" alt="demo">
</div>

RAG-DOCS is a proof of concept document search engine that uses `RAG` (Retrieval Augmented Generation) architecture to deliver query completions, the system enables users to upload documents, perform semantic searches, and receive AI-generated responses based on relevant context extracted from the uploaded documents.

The architecture consists of four core microservices:
- **UI Service**: Intuitive interface for document management and chatting interactions
- **Retriever Service**: Executes vector similarity searches to identify relevant document sections based on user queries
- **Embedder Service**: Processes documents to generate vector embeddings and store at PostgresSQL vector database
- **LLM Service**: Provides AI-generated completions using Ollama or OpenAI language models

Thi implementation aim for microservices architecture and uses FastAPI for the backend services (retriever/embedder), Gradio for the front-end interface, MinIO for document storage, PostgreSQL with pgvector for vector storage and search, and supports both Ollama (local) and OpenAI (cloud) LLMs for generating responses. For a detailed workflow explanation, see the [How it works?](#how-it-works-) section.

The repository includes a demo data about a fictional company "NexusTech" with sample HR policies and API documentation, showcasing the system's ability to extract and synthesize information across multiple document types.

By default RAG-DOCS utilizes the `all-MiniLM-L6-v2` embedding model from Ollama, which offers a good balance of performance and resource efficiency (requiring only 2GB RAM), while this model provides reasonable performance, it may be less precise than OpenAI's embedding models eg, which is why the default similarity threshold is set to 0.25. This threshold can be adjusted through environment variables to fine-tune retrieval precision.

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

### How it works ?

1. **Interface (UI)**:
   - Users interact with the system through the UI service (Gradio)

2. **Document Processing**:
   - New documents are uploaded to MinIO storage via the UI
   - MinIO sends webhook notifications to the Embedder service
   - Embedder creates vector embeddings and stores them in the Postgres vector database

3. **Query Processing**:
   - UI sends queries to the Retriever service when chat is initiated
   - Retriever performs vector similarity search in Postgres
   - UI sends prompts to Ollama LLM along with retrieved context
   - Ollama returns generated responses to the UI




## Getting Started

### Hardware requirements

- Minimum:
   - 2 CPU
   - 4~8 GB RAM 

- Recommended:
   - A GPU with >6GB VRAM for better performance

> Requirements will depend most if you are using a local model (Ollama) or OpenAI API, if using local models GPU is highly recommended.

### Pre-requisites

Before you begin, make sure you have:

- Git
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

<details>
<summary>Managing Ollama Models</summary>

If you’re using local Ollama models, ensure the required model is available:

To check available models: `curl http://localhost:11434/api/tags -s | jq .models[].name`

Where `localhost:11434` is the Ollama service endpoint.

To download a model:
- Via API: `curl -X POST http://localhost:11434/api/pull -d '{"name": "llama3.1:8b"}'`
- Via UI: Go to System Status tab and click "Download Model"

Note: This example uses llama3.1:8b which requires ~8GB VRAM. Consider smaller models for limited hardware.
</details>

#### Using OpenAI as an Alternative

If you prefer using OpenAI instead of local Ollama models, follow these steps:

##### 1. Configure OpenAI API

Edit the `docker-compose.openai.yaml` file to set your API key:

```yaml

ui:
   environment:
      LLM_PROVIDER: "openai"
      OPENAI_API_BASE: "https://api.openai.com/v1/"
      OPENAI_API_KEY: "your-api-key" # change here
```


##### 2. Launch with OpenAI

Start the system using the OpenAI configuration:

```bash
docker-compose -f docker-compose.openai.yaml up -d --build
```

### Interacting with RAG-DOCS

1. **Upload a Document**: Use the UI to upload your TXT or PDF file.
2. **Start a Chat Session**: Initiate a chat to query the content of your document.
3. **Ask Questions**: Interact with your document by asking questions.

### Kubernetes Deployment 

For deploying on Kubernetes:
- Refer to the [Kubernetes Deployment Guide](charts/rag-docs/README.md) using Helm for detailed instructions.
- Customize your deployment using the values provided in the helm directory.

###  🚧 Monitoring - WIP 🚧

Monitoring with prometheus and grafana soon.

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

### Service Interfaces

| Service | Interface Port |
|---------|---------------|
| UI Service | 3000 |
| Retriever Service | 6000 |
| Embedder Service | 5000 |
| Postgres | 5432 |
| MinIO | 9000, 9001 |
| Ollama LLM | 11434 |

### Screenshots

<p align="center">
<img src="assets/images/ui-1.jpg">
<img src="assets/images/ui-2.jpg">
<img src="assets/images/ui-3.jpg">
</p>

### Troubleshooting and FAQs

1. **GPU Support**: Verify that the NVIDIA Docker runtime is correctly configured. Check the [official documentation](https://docs.docker.com/config/containers/resource_constraints/#access-an-nvidia-gpu) for more information.

2. **Model Download**: If you encounter issues with model download, check the Ollama service logs for more information.

3. **Critical TIMEOUT errors on both embedder and retriever services**: This can happen if the hardware requirements are not met, altho if you wait a bit the services should start working.

4. **Connection Issues**: If you're unable to connect to services, verify these ports are accessible:
   - UI Service: 3000
   - Retriever Service: 6000
   - Embedder Service: 5000
   - PostgreSQL: 5432
   - MinIO: 9000 (API)
   - Ollama: 11434

5. **Performance Issues**: 
   - If the system is slow or unresponsive, ensure your hardware meets at least the minimum requirements (2 CPU cores, 4GB RAM)
   - For smoother performance with larger documents or multiple queries, consider upgrading to the recommended specs (including GPU with 6GB+ VRAM)
   - Consider using a smaller language model (tinyllama eg) if you have hardware constraints

6. **File Processing Issues**:
   - If uploaded documents aren't appearing in search results, check the embedder logs for processing errors
   - Verify MinIO webhook notifications are correctly configured by checking the embedder logs for event receipts
   - Ensure uploaded files are in supported formats (PDF, TXT)

### License

This project is available under the [MIT License](https://github.com/daviaraujocc/rag-docs/blob/main/LICENSE).


### TODO

- ~~[ ] Add Helm charts for Kubernetes deployment~~
- [ ] Implement caching for faster responses
- [ ] Add support for more document formats
- [ ] Implement metrics and monitoring