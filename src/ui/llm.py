import os
import requests
import logging
import time
import json
from typing import Dict, Any, Optional, Tuple, List
from llama_index.llms.openai import OpenAI
from llama_index.llms.ollama import Ollama
import config

logger = logging.getLogger(__name__)

def get_available_ollama_models(base_url: str = None) -> List[str]:
    """Get a list of available models from Ollama server."""
    if base_url is None:
        base_url = config.OLLAMA_BASE_URL
        
    try:
        response = requests.get(f"{base_url}/api/tags")
        if response.status_code == 200:
            models = response.json().get("models", [])
            return [model["name"] for model in models]
        else:
            logger.error(f"Failed to get models from Ollama: {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error connecting to Ollama: {str(e)}")
        return []

def download_ollama_model(base_url: str = None, model_name: str = None, progress_callback=None) -> Tuple[bool, str]:
    """
    Download a model from Ollama server.
    
    Args:
        base_url: Ollama API base URL
        model_name: The model to download
        progress_callback: Optional callback function that receives progress updates (0-100)
    
    Returns:
        (success, message)
    """
    if base_url is None:
        base_url = config.OLLAMA_BASE_URL
    if model_name is None:
        model_name = config.OLLAMA_MODEL
        
    try:
        response = requests.post(
            f"{base_url}/api/pull",
            json={"name": model_name},
            stream=True
        )
        
        if response.status_code != 200:
            return False, f"Failed to start model download: {response.status_code}"
            
        if progress_callback:
            progress_callback({"status": "starting", "progress": 0})
            
        total = 0
        completed = 0
        last_progress = -1
        
        for line in response.iter_lines():
            if line:
                try:
                    data = line.decode('utf-8')
                    data_json = json.loads(data)
                    
                    if "total" in data_json:
                        total = data_json.get("total", 0)
                    
                    if "completed" in data_json:
                        completed = data_json.get("completed", 0)
                    
                    progress = 0
                    if total > 0:
                        progress = min(int((completed / total) * 100), 99)
                    
                    if progress != last_progress and progress_callback:
                        progress_callback({"status": "downloading", "progress": progress})
                        last_progress = progress
                        
                except Exception as e:
                    logger.warning(f"Error parsing progress data: {str(e)}")
        
        if progress_callback:
            progress_callback({"status": "completed", "progress": 100})
            
        return True, f"Successfully downloaded model {model_name}"
        
    except Exception as e:
        logger.error(f"Error downloading model: {str(e)}")
        if progress_callback:
            progress_callback({"status": "error", "progress": 0})
        return False, f"Error downloading model: {str(e)}"

def check_ollama_model(base_url: str = None, model_name: str = None) -> bool:
    """Check if a model exists on the Ollama server."""
    if base_url is None:
        base_url = config.OLLAMA_BASE_URL
    if model_name is None:
        model_name = config.OLLAMA_MODEL
        
    available_models = get_available_ollama_models(base_url)
    return model_name in available_models

def create_llm(provider: Optional[str] = None, **kwargs):
    """
    Factory function to create an LLM instance based on provider.
    
    Args:
        provider: The LLM provider ('openai' or 'ollama'). If None, reads from config.
        **kwargs: Additional configuration to pass to the LLM constructor
    
    Returns:
        An LLM instance from llama_index
    """
    if provider is None:
        provider = config.LLM_PROVIDER
    
    if provider == "openai":
        api_base = kwargs.get("api_base", config.OPENAI_API_BASE)
        api_key = kwargs.get("api_key", config.OPENAI_API_KEY)
        model = kwargs.get("model", config.OPENAI_MODEL)
        
        return OpenAI(
            api_key=api_key,
            api_base=api_base,
            model=model,
            temperature=kwargs.get("temperature", 0.7)
        )
    
    elif provider == "ollama":
        base_url = kwargs.get("base_url", config.OLLAMA_BASE_URL)
        model = kwargs.get("model", config.OLLAMA_MODEL)
        
        return Ollama(
            base_url=base_url,
            model=model,
            temperature=kwargs.get("temperature", 0.7)
        )
    
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
