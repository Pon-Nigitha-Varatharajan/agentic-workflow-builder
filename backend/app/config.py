from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    unbound_api_key: str = os.getenv("UNBOUND_API_KEY", "")
    unbound_chat_url: str = os.getenv("UNBOUND_CHAT_URL", "")
    unbound_timeout_seconds: int = int(os.getenv("UNBOUND_TIMEOUT_SECONDS", "60"))

settings = Settings()

if not settings.unbound_api_key:
    print("⚠️  UNBOUND_API_KEY is not set. Add it to backend/.env")
if not settings.unbound_chat_url:
    print("⚠️  UNBOUND_CHAT_URL is not set. Add it to backend/.env")