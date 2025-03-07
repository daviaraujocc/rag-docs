import os
from typing import Dict, Any, Optional
from llama_index.llms.openai import OpenAI
from llama_index.llms.ollama import Ollama

def create_llm(provider: Optional[str] = None, **kwargs):
    """
    Factory function to create an LLM instance based on provider.
    
    Args:
        provider: The LLM provider ('openai' or 'ollama'). If None, reads from LLM_PROVIDER env var.
        **kwargs: Additional configuration to pass to the LLM constructor
    
    Returns:
        An LLM instance from llama_index
    """
    if provider is None:
        provider = os.getenv("LLM_PROVIDER", "openai").lower()
    
    if provider == "openai":
        api_base = kwargs.get("api_base", os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"))
        api_key = kwargs.get("api_key", os.getenv("OPENAI_API_KEY", ""))
        model = kwargs.get("model", os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"))
        
        return OpenAI(
            api_key=api_key,
            api_base=api_base,
            model=model,
            temperature=kwargs.get("temperature", 0.7)
        )
    
    elif provider == "ollama":
        base_url = kwargs.get("base_url", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
        model = kwargs.get("model", os.getenv("OLLAMA_MODEL", "tinyllama"))
        
        return Ollama(
            base_url=base_url,
            model=model,
            temperature=kwargs.get("temperature", 0.7)
        )
    
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
