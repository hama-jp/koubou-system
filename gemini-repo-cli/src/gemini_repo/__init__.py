from .base_api import BaseRepoAPI

# Lazy imports to avoid requiring all dependencies
def get_gemini_api():
    """Lazy import for GeminiRepoAPI - only imports when needed"""
    from .gemini_api import GeminiRepoAPI, DEFAULT_GEMINI_MODEL
    return GeminiRepoAPI, DEFAULT_GEMINI_MODEL

def get_ollama_api():
    """Lazy import for OllamaRepoAPI - only imports when needed"""
    from .ollama_api import OllamaRepoAPI, DEFAULT_OLLAMA_MODEL, DEFAULT_OLLAMA_HOST
    return OllamaRepoAPI, DEFAULT_OLLAMA_MODEL, DEFAULT_OLLAMA_HOST

__all__ = [
    "BaseRepoAPI",
    "get_gemini_api",
    "get_ollama_api",
]
