import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import CORS_ORIGINS, IS_DEV, UPLOAD_DIR
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
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Adicionado por último para ficar por fora: recusa corpos grandes antes de qualquer leitura
app.add_middleware(LimiteCorpoMiddleware)

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
    return {"service": "OneCheck API", "docs": "/docs", "health": f"{prefix}/health"}
