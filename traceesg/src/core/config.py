import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    MODEL_NAME = "gpt-4o-mini"
    EMBEDDING_MODEL = "text-embedding-3-small"
    
    if not OPENAI_API_KEY:
        raise ValueError("A chave OPENAI_API_KEY não foi encontrada no arquivo .env")