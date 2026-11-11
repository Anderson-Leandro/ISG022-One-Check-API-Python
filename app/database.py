import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL
from app.cpf_cifrado import TAMANHO_COLUNA, cifrar_cpfs_em_texto

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
    # Importado aqui: app.log_append_only importa app.models, que importa este módulo
    from app.log_append_only import exclusao_autorizada, instalar

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
            # SEC-031: o CPF cifrado não cabe em VARCHAR(14). O SQLite não confere o tamanho
            tamanho = next(
                (getattr(c["type"], "length", None) for c in insp.get_columns("usuarios") if c["name"] == "cpf"), None
            )
            if tamanho and tamanho < TAMANHO_COLUNA:
                if engine.dialect.name == "postgresql":
                    conn.execute(text(f"ALTER TABLE usuarios ALTER COLUMN cpf TYPE VARCHAR({TAMANHO_COLUNA})"))
                elif engine.dialect.name == "mysql":
                    conn.execute(text(f"ALTER TABLE usuarios MODIFY cpf VARCHAR({TAMANHO_COLUNA})"))
            # Cifra o que ainda está em texto; a troca de chave é feita pelo scripts/rotacionar_chave_cpf.py
            cifrados = cifrar_cpfs_em_texto(conn)
            if cifrados:
                logging.getLogger(__name__).info("CPF: %d registro(s) em texto cifrado(s)", cifrados)

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

        # Detecção de reuso do refresh trocado (SEC-027)
        if "auth_refresh_tokens" in tables:
            cols = {c["name"] for c in insp.get_columns("auth_refresh_tokens")}
            if "usado_em" not in cols:
                conn.execute(text("ALTER TABLE auth_refresh_tokens ADD COLUMN usado_em TIMESTAMP"))

        # Exclusão lógica (US-015, ADR-0008)
        exclusao = {
            "contratos": (
                "ALTER TABLE contratos ADD COLUMN excluido_em TIMESTAMP",
                "ALTER TABLE contratos ADD COLUMN excluido_por VARCHAR(36) REFERENCES usuarios(id)",
            ),
            "checklists": (
                "ALTER TABLE checklists ADD COLUMN excluido_em TIMESTAMP",
                "ALTER TABLE checklists ADD COLUMN excluido_por VARCHAR(36) REFERENCES usuarios(id)",
            ),
            "problemas": (
                "ALTER TABLE problemas ADD COLUMN excluido_em TIMESTAMP",
                "ALTER TABLE problemas ADD COLUMN excluido_por VARCHAR(36) REFERENCES usuarios(id)",
            ),
        }
        for tabela, (add_em, add_por) in exclusao.items():
            if tabela in tables:
                cols = {c["name"] for c in insp.get_columns(tabela)}
                if "excluido_em" not in cols:
                    conn.execute(text(add_em))
                if "excluido_por" not in cols:
                    conn.execute(text(add_por))

        if "log_operacao" in tables:
            cols = {c["name"] for c in insp.get_columns("log_operacao")}
            if "payload" not in cols:
                conn.execute(text("ALTER TABLE log_operacao ADD COLUMN payload JSON"))
            if "ip" not in cols:
                conn.execute(text("ALTER TABLE log_operacao ADD COLUMN ip VARCHAR(45)"))
            # SEC-025: os triggers append-only, também em bancos criados antes deles (idempotente)
            instalar(conn)
            # SEC-019: os logins falhos antigos guardavam o texto digitado no campo e-mail (às vezes uma senha).
            # É a única alteração autorizada fora da retenção
            with exclusao_autorizada(conn, "migracao SEC-019"):
                conn.execute(
                    text(
                        "UPDATE log_operacao SET detalhes = NULL WHERE acao = 'login_falho' AND detalhes LIKE 'email:%'"
                    )
                )
