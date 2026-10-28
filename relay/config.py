import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    database_url: str = os.getenv('DATABASE_URL', 'postgresql://relay_app:relay_app@localhost:5432/postgres')
    admin_url: str = os.getenv('ADMIN_DATABASE_URL', 'postgresql://postgres:relay@localhost:5432/postgres')
    ollama_url: str = os.getenv('OLLAMA_URL', 'http://localhost:11434')
    triage_model: str = os.getenv('TRIAGE_MODEL', 'qwen2.5:1.5b')
    draft_model: str = os.getenv('DRAFT_MODEL', 'llama3.2:3b')
    embed_model: str = os.getenv('EMBED_MODEL', 'nomic-embed-text')
    ticket_budget: int = int(os.getenv('TICKET_TOKEN_BUDGET', '30000'))
    run_budget: int = int(os.getenv('RUN_TOKEN_BUDGET', '1000000'))
    max_output: int = int(os.getenv('MAX_OUTPUT_TOKENS', '350'))
    timeout: int = int(os.getenv('MODEL_TIMEOUT', '180'))
    lease_seconds: int = int(os.getenv('LEASE_SECONDS', '600'))
    max_attempts: int = int(os.getenv('MAX_ATTEMPTS', '3'))
    retry_base: float = float(os.getenv('RETRY_BASE_SECONDS', '2'))
    seed: int = int(os.getenv('SEED', '7'))

TENANTS = ('northwind', 'harbor')
