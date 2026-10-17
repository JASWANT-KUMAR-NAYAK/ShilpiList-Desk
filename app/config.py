
import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

# Load variables from the project's .env file
load_dotenv()

@dataclass(frozen=True)
class Settings:
    base_url: str = os.getenv("LLM_BASE_URL", "https://ollama.com/v1")
    model: str = os.getenv("LLM_MODEL", "gemma4:31b")
    api_key: str = os.getenv("LLM_API_KEY", "")
    data_dir: str = os.getenv("DATA_DIR", "data")
    max_image_px: int = int(os.getenv("MAX_IMAGE_PX", "1024"))
    timeout_s: float = float(os.getenv("LLM_TIMEOUT_S", "300"))

settings = Settings()
