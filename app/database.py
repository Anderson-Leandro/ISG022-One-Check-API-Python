from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL

_connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args=_connect_args,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema_updates() -> None:
    """Cria tabelas e adiciona colunas novas em bancos já existentes."""
    Base.metadata.create_all(bind=engine)
    insp = inspect(engine)
    tables = set(insp.get_table_names())

    with engine.begin() as conn:
        if "usuarios" in tables:
            cols = {c["name"] for c in insp.get_columns("usuarios")}
            if "mfa_secret_pendente" not in cols:
                conn.execute(text("ALTER TABLE usuarios ADD COLUMN mfa_secret_pendente VARCHAR(64)"))
            if "token_version" not in cols:
                conn.execute(text("ALTER TABLE usuarios ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0"))

        if "enderecos" in tables:
            cols = {c["name"] for c in insp.get_columns("enderecos")}
            if "latitude" not in cols:
                conn.execute(text("ALTER TABLE enderecos ADD COLUMN latitude FLOAT"))
            if "longitude" not in cols:
                conn.execute(text("ALTER TABLE enderecos ADD COLUMN longitude FLOAT"))
            if "bloco" not in cols:
                conn.execute(text("ALTER TABLE enderecos ADD COLUMN bloco VARCHAR(50)"))
            if "andar" not in cols:
                conn.execute(text("ALTER TABLE enderecos ADD COLUMN andar VARCHAR(50)"))
            if "ativo" not in cols:
                conn.execute(text("ALTER TABLE enderecos ADD COLUMN ativo BOOLEAN DEFAULT 1"))

        if "imoveis" in tables:
            cols = {c["name"] for c in insp.get_columns("imoveis")}
            if "ativo" not in cols:
                conn.execute(text("ALTER TABLE imoveis ADD COLUMN ativo BOOLEAN DEFAULT 1"))

        if "problemas" in tables:
            cols = {c["name"] for c in insp.get_columns("problemas")}
            if "comodo_id" not in cols:
                conn.execute(text("ALTER TABLE problemas ADD COLUMN comodo_id VARCHAR(36)"))
            if "foto_url" not in cols:
                conn.execute(text("ALTER TABLE problemas ADD COLUMN foto_url VARCHAR(500)"))

        if "log_operacao" in tables:
            cols = {c["name"] for c in insp.get_columns("log_operacao")}
            if "payload" not in cols:
                conn.execute(text("ALTER TABLE log_operacao ADD COLUMN payload JSON"))
            if "ip" not in cols:
                conn.execute(text("ALTER TABLE log_operacao ADD COLUMN ip VARCHAR(45)"))
