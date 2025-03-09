# RAG-DOCS Helm Chart

This Helm chart deploys RAG-DOCS - a document search engine that uses RAG (Retrieval Augmented Generation) architecture to provide completions for your queries.

## Prerequisites

- Kubernetes 1.30+
- Helm 3.2.0+
- PV provisioner support in the underlying infrastructure (if persistence is enabled)

## Getting Started

### Add the repository

```bash
helm repo add rag-docs https://daviaraujocc.github.io/rag-docs/
helm repo update
```


### Install the chart

```bash
helm install rag-docs rag-docs/rag-docs
```

## Configuration

The following table lists the configurable parameters of the RAG-DOCS chart and their default values.

### Global Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `nameOverride` | Override the name of the chart | `""` |
| `fullnameOverride` | Override the full name of the chart | `""` |
| `commonLabels` | Labels to apply to all resources | `{}` |
| `commonAnnotations` | Annotations to apply to all resources | `{}` |
| `imagePullSecrets` | Global image pull secrets | `[]` |
| `nodeSelector` | Global node selector | `{}` |
| `tolerations` | Global tolerations | `[]` |
| `affinity` | Global affinity | `{}` |

For complete parameter listing and usage examples, please refer to [values.yaml](values.yaml).

## LLM Options

The chart supports two LLM providers:

### Ollama (Default)

RAG-DOCS uses Ollama by default with llama3.1:8b model. You can customize it with:

```yaml
ui:
  env:
    LLM_PROVIDER: "ollama"
    OLLAMA_BASE_URL: "http://rag-docs-ollama:11434"
    OLLAMA_MODEL: "llama3.1:8b"
```

### OpenAI

To use OpenAI instead:

```yaml
ui:
  env:
    LLM_PROVIDER: "openai"
    OPENAI_API_BASE: "https://api.openai.com/v1/"
    OPENAI_API_KEY: "your-api-key-here"
    OPENAI_MODEL: "gpt-3.5-turbo"
```

## Persistence

The chart supports persistence for:

- PostgreSQL database
- MinIO storage
- Ollama models

You can configure persistence options for each component in `values.yaml`.
