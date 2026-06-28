import os
from dotenv import load_dotenv

# Load configurations from .env
load_dotenv()

class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GITHUB_TOKEN = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN") or os.getenv("GITHUB_TOKEN")

    # LLM backend: "openai" (default) or "ollama"
    LLM_BACKEND = os.getenv("LLM_BACKEND", "openai").lower()

    # Ollama settings
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

    # Default model depends on backend
    DEFAULT_MODEL = (
        os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        if LLM_BACKEND == "ollama"
        else os.getenv("OPENAI_MODEL", "gpt-4o")
    )

    @classmethod
    def validate(cls):
        missing = []
        if cls.LLM_BACKEND == "openai" and not cls.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")
        if not cls.GITHUB_TOKEN:
            missing.append("GITHUB_PERSONAL_ACCESS_TOKEN (or GITHUB_TOKEN)")

        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}. Please define them in a .env file.")
