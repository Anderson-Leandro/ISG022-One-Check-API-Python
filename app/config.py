import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

# ONECHECK_SEM_DOTENV=1 ignora o arquivo de configuração local: execuções descartáveis (testes, collection)
# não herdam limites nem segredos da máquina (TK-020)
if os.getenv("ONECHECK_SEM_DOTENV") != "1":
    load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Render Postgres usa postgres:// — SQLAlchemy 2.x exige postgresql://
_db_url = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'onecheck.db'}")
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)
DATABASE_URL = _db_url

# Secure by default: sem APP_ENV, vale a regra de produção
APP_ENV = os.getenv("APP_ENV", "").strip().lower() or "production"
IS_DEV = APP_ENV in ("development", "dev", "local", "test")
# SEC-029: o login marca senha_expirada quando a senha não passa na política, salvo em desenvolvimento, onde
# as contas do seed usam senhas públicas por desenho (decisão do PO em 2026-11-12). Nos testes, marca
MARCAR_SENHA_FRACA = not IS_DEV or APP_ENV == "test"

MIN_SECRET_LEN = 32
# Valores que já estiveram no repositório (fallback antigo e exemplo do README): são públicos
_PUBLIC_JWT_SECRETS = {"onecheck-dev-secret-change-me", "sua_chave_secreta_jwt_super_segura"}


def _jwt_secret() -> str:
    valor = os.getenv("JWT_SECRET", "").strip()
    publico = not valor or valor in _PUBLIC_JWT_SECRETS
    if IS_DEV:
        if publico:
            # Tokens deixam de valer a cada reinício; serve só para desenvolvimento
            logging.getLogger(__name__).warning(
                "JWT_SECRET ausente ou público: usando valor aleatório (APP_ENV=%s)", APP_ENV
            )
            return secrets.token_urlsafe(48)
        return valor
    if publico or len(valor) < MIN_SECRET_LEN:
        raise RuntimeError(
            f"JWT_SECRET ausente, público ou com menos de {MIN_SECRET_LEN} caracteres. "
            'Gere um com: python -c "import secrets; print(secrets.token_urlsafe(48))" '
            "(ou use APP_ENV=development localmente)."
        )
    return valor


JWT_SECRET = _jwt_secret()

# Chaves do CPF em repouso (SEC-031, ADR-0014), separadas por vírgula: a primeira cifra, todas decifram.
# Para rotacionar, ver o scripts/rotacionar_chave_cpf.py (a nova entra primeiro só para leitura).
# Em desenvolvimento e teste, sem valor, vale uma chave fixa e pública (o banco local continua legível
# entre reinícios); fora deles, a API não sobe sem uma chave de 32+ caracteres.
_CPF_CHAVE_DEV = "onecheck-chave-de-desenvolvimento-do-cpf-publica"


def _cpf_chaves() -> list[str]:
    chaves = [c.strip() for c in os.getenv("CPF_CHAVES", "").split(",") if c.strip()]
    if IS_DEV:
        if not chaves:
            logging.getLogger(__name__).warning("CPF_CHAVES ausente: usando a chave pública de desenvolvimento")
            return [_CPF_CHAVE_DEV]
        return chaves
    if not chaves or chaves[0] == _CPF_CHAVE_DEV or any(len(c) < MIN_SECRET_LEN for c in chaves):
        raise RuntimeError(
            f"CPF_CHAVES ausente, pública ou com chave de menos de {MIN_SECRET_LEN} caracteres. "
            'Gere uma com: python -c "import secrets; print(secrets.token_urlsafe(48))" '
            "(ou use APP_ENV=development localmente)."
        )
    return chaves


CPF_CHAVES = _cpf_chaves()
JWT_ALGORITHM = "HS256"
JWT_ACCESS_MINUTES = int(os.getenv("JWT_ACCESS_MINUTES", "60"))
JWT_REFRESH_DAYS = int(os.getenv("JWT_REFRESH_DAYS", "30"))

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
# Corpo das requisições que não são multipart (JSON); uploads usam MAX_UPLOAD_MB
MAX_BODY_KB = int(os.getenv("MAX_BODY_KB", "1024"))

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

# Sem SEED_SECRET (ou com o antigo valor padrão, que é público) as rotas /admin/* ficam desabilitadas
_PUBLIC_SEED_SECRETS = {"onecheck-seed-dev"}
_seed_secret = os.getenv("SEED_SECRET", "").strip()
SEED_SECRET = "" if _seed_secret in _PUBLIC_SEED_SECRETS else _seed_secret
if SEED_SECRET and not IS_DEV and len(SEED_SECRET) < MIN_SECRET_LEN:
    raise RuntimeError(
        f"SEED_SECRET precisa ter pelo menos {MIN_SECRET_LEN} caracteres (ou ficar vazio para desabilitar /admin/*)."
    )

# force=true e refresh_data apagam dados: só com opt-in explícito
SEED_ALLOW_DESTRUCTIVE = os.getenv("SEED_ALLOW_DESTRUCTIVE", "false").strip().lower() in ("1", "true", "yes")

# Origens do front, separadas por vírgula. Sem valor, em produção nenhum site de outra
# origem chama a API pelo navegador; em desenvolvimento, todas
_cors = os.getenv("CORS_ORIGINS", "").strip() or ("*" if IS_DEV else "")
CORS_ORIGINS = ["*"] if _cors == "*" else [o.strip().rstrip("/") for o in _cors.split(",") if o.strip()]

# /docs, /redoc e /openapi.json: ligados só em desenvolvimento, salvo DOCS_ENABLED=true
_docs = os.getenv("DOCS_ENABLED", "").strip().lower()
DOCS_ENABLED = _docs in ("1", "true", "yes") if _docs else IS_DEV

# Limite de tentativas falhas (login, MFA, reautenticação) por conta e por IP, numa janela deslizante
RATE_LIMIT_FALHAS_CONTA = int(os.getenv("RATE_LIMIT_FALHAS_CONTA", "5"))
RATE_LIMIT_FALHAS_IP = int(os.getenv("RATE_LIMIT_FALHAS_IP", "20"))
RATE_LIMIT_JANELA_MIN = int(os.getenv("RATE_LIMIT_JANELA_MIN", "15"))

# Consulta de senhas vazadas no Have I Been Pwned, por k-anonymity (SEC-030). Ligada por padrão; false desliga
_senha_vazada = os.getenv("SENHA_VAZADA_CONSULTA", "").strip().lower()
SENHA_VAZADA_CONSULTA = _senha_vazada in ("1", "true", "yes", "on") if _senha_vazada else True

# Proxies confiáveis na frente da API que acrescentam o IP de quem os chamou ao X-Forwarded-For
# (SEC-017, ADR-0015). 0, o padrão: o cabeçalho é ignorado e vale o IP da conexão. No Render, 3 (ADR-0015)
PROXY_SALTOS = int(os.getenv("PROXY_SALTOS", "0"))
if PROXY_SALTOS < 0:
    raise RuntimeError("PROXY_SALTOS não pode ser negativo.")

# Retenção do log_operacao (tem IP e e-mail). O Marco Civil (art. 15) exige guardar
# registros de acesso por 6 meses, então o mínimo é 180 dias
LOG_RETENCAO_MIN_DIAS = 180
LOG_RETENCAO_DIAS = int(os.getenv("LOG_RETENCAO_DIAS", "365"))
if LOG_RETENCAO_DIAS < LOG_RETENCAO_MIN_DIAS:
    raise RuntimeError(
        f"LOG_RETENCAO_DIAS precisa ser de pelo menos {LOG_RETENCAO_MIN_DIAS} dias (registros de acesso, Marco Civil art. 15)."
    )
