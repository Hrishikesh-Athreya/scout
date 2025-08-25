import os
from dotenv import load_dotenv

load_dotenv()  # loads from .env into environment variables

FOXIT_CLIENT_ID = os.getenv("FOXIT_CLIENT_ID") or ""
FOXIT_CLIENT_SECRET = os.getenv("FOXIT_CLIENT_SECRET") or ""
FOXIT_DOCGEN_URL = os.getenv("FOXIT_DOCGEN_URL") or ""
FOXIT_PDF_SERVICES_URL = os.getenv("FOXIT_PDF_SERVICES_URL") or ""
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or ""
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or ""
GEMINI_ENDPOINT = os.getenv("GEMINI_ENDPOINT") or ""
