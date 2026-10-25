import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Render Postgres usa postgres:// — SQLAlchemy 2.x exige postgresql://
_db_url = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'onecheck.db'}")
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)
DATABASE_URL = _db_url

JWT_SECRET = os.getenv("JWT_SECRET", "onecheck-dev-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_MINUTES = int(os.getenv("JWT_ACCESS_MINUTES", "60"))
JWT_REFRESH_DAYS = int(os.getenv("JWT_REFRESH_DAYS", "30"))

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

# Sem SEED_SECRET (ou com o antigo valor padrão, que é público) as rotas /admin/* ficam desabilitadas
_PUBLIC_SEED_SECRETS = {"onecheck-seed-dev"}
_seed_secret = os.getenv("SEED_SECRET", "").strip()
SEED_SECRET = "" if _seed_secret in _PUBLIC_SEED_SECRETS else _seed_secret

# force=true e refresh_data apagam dados: só com opt-in explícito
SEED_ALLOW_DESTRUCTIVE = os.getenv("SEED_ALLOW_DESTRUCTIVE", "false").strip().lower() in ("1", "true", "yes")

_cors = os.getenv("CORS_ORIGINS", "*")
CORS_ORIGINS = ["*"] if _cors.strip() == "*" else [o.strip() for o in _cors.split(",") if o.strip()]
