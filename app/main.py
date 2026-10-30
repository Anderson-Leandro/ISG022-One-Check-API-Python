import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.auditoria import IpRequisicaoMiddleware
from app.cabecalhos import CabecalhosSegurancaMiddleware
from app.config import CORS_ORIGINS, DOCS_ENABLED, IS_DEV, UPLOAD_DIR
from app.database import Base, SessionLocal, ensure_schema_updates, engine
from app.limite_corpo import LimiteCorpoMiddleware
from app.routers import (
    admin,
    agendamentos,
    auth_router,
    checklists,
    contratos,
    dashboard,
    health,
    imoveis,
    problemas,
    usuarios,
)
from app.seed_service import contas_com_credenciais_publicas


@asynccontextmanager
async def lifespan(app: FastAPI):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ensure_schema_updates()
    if not IS_DEV:
        _alertar_credenciais_publicas()
        if not CORS_ORIGINS:
            logging.getLogger(__name__).warning(
                "CORS_ORIGINS não definido: navegadores em outra origem (o front) não conseguem chamar a API."
            )
    yield


def _alertar_credenciais_publicas() -> None:
    with SessionLocal() as db:
        emails = [u.email for u in contas_com_credenciais_publicas(db)]
    if emails:
        logging.getLogger(__name__).critical(
            "SEGURANÇA: contas com senha ou segredo MFA de demonstração (públicos no repositório): %s. "
            "Rode scripts/rotacionar_credenciais_demo.py --aplicar.",
            ", ".join(emails),
        )


app = FastAPI(
    title="OneCheck API",
    version="1.0.0",
    description="API REST para integração Web + Mobile OneCheck",
    lifespan=lifespan,
    # Em produção a documentação interativa fica desligada (DOCS_ENABLED=true liga)
    docs_url="/docs" if DOCS_ENABLED else None,
    redoc_url="/redoc" if DOCS_ENABLED else None,
    openapi_url="/openapi.json" if DOCS_ENABLED else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    # A autenticação é por header Bearer: o navegador não precisa enviar cookies
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    # Lidos pelo front: espera do limite de tentativas e nome do PDF do laudo
    expose_headers=["Retry-After", "Content-Disposition"],
)
# IP de origem para a trilha de auditoria (log_operacao)
app.add_middleware(IpRequisicaoMiddleware)
# Adicionado depois do CORS para ficar por fora: recusa corpos grandes antes de qualquer leitura
app.add_middleware(LimiteCorpoMiddleware)
# O mais externo: os cabeçalhos valem também para as respostas 413 e 400 do limite de corpo
app.add_middleware(CabecalhosSegurancaMiddleware)

prefix = "/api/v1"

app.include_router(health.router, prefix=prefix)
app.include_router(auth_router.router, prefix=prefix)
app.include_router(usuarios.router, prefix=prefix)
app.include_router(imoveis.router, prefix=prefix)
app.include_router(contratos.router, prefix=prefix)
app.include_router(agendamentos.router, prefix=prefix)
app.include_router(checklists.router, prefix=prefix)
app.include_router(problemas.router, prefix=prefix)
app.include_router(dashboard.router, prefix=prefix)
app.include_router(admin.router, prefix=prefix)


@app.get("/")
def root():
    return {"service": "OneCheck API", "docs": "/docs" if DOCS_ENABLED else None, "health": f"{prefix}/health"}
