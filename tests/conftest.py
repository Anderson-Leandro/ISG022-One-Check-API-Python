"""
Infraestrutura global de testes — fixtures de banco, client HTTP, usuários e dados base.

Estratégia de isolamento:
  - Uma conexão por teste, envolta em uma transação explícita.
  - A Session usa join_transaction_mode="create_savepoint" para que commits de
    rotas criem SAVEPOINTs em vez de commits reais.
  - Ao final de cada teste, a transação externa é revertida, apagando todos os
    dados criados durante o teste sem custo de recriação de schema.
"""
import io
import os
import shutil
import tempfile

import bcrypt
import pyotp
import pytest
from datetime import date
from PIL import Image
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

# DATABASE_URL deve ser definida ANTES de qualquer importação da app.
# Em CI: variável TEST_DATABASE_URL aponta para o PostgreSQL do service.
# Localmente: cai no SQLite de arquivo para conveniência.
_raw_url = os.getenv("TEST_DATABASE_URL", "sqlite:///./onecheck_test.db")
if _raw_url.startswith("postgres://"):
    _raw_url = _raw_url.replace("postgres://", "postgresql://", 1)
os.environ["DATABASE_URL"] = _raw_url
os.environ.setdefault("APP_ENV", "test")
# Os testes gravam e, ao final, apagam UPLOAD_DIR: nunca apontar para o uploads/ real do projeto
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="onecheck-test-uploads-")

# Importações da app somente após definir DATABASE_URL
from app.main import app  # noqa: E402
from app.config import UPLOAD_DIR  # noqa: E402
from app.database import Base, engine as test_engine, get_db  # noqa: E402
from app.models import (  # noqa: E402
    AgendamentoVistoria,
    Checklist,
    Contrato,
    Imovel,
    ImovelComodo,
    ItemVistoria,
    Usuario,
)
from app.auth import create_access_token  # noqa: E402

# ── Constantes de teste ─────────────────────────────────────────────────────────

MFA_TEST_SECRET = "JBSWY3DPEHPK3PXP"
TEST_SENHA = "senha123"

# Hash calculado uma vez com custo baixo (rounds=4) para acelerar os testes.
# bcrypt padrão usa rounds=12, o que tornaria cada fixture lenta.
_SENHA_HASH = bcrypt.hashpw(TEST_SENHA.encode(), bcrypt.gensalt(rounds=4)).decode()


# ── Helpers exportados para uso nos módulos de teste ────────────────────────────

def auth(token: str) -> dict:
    """Monta o header Authorization Bearer para requisições de teste."""
    return {"Authorization": f"Bearer {token}"}


def totp_now() -> str:
    """Retorna o código TOTP atual gerado com o secret fixo de teste."""
    return pyotp.TOTP(MFA_TEST_SECRET).now()


def small_image_bytes() -> bytes:
    """Retorna bytes de uma imagem PNG válida (1x1 pixel).

    Gerada pelo Pillow: os uploads validam o conteúdo, e o PNG fixo usado antes
    tinha CRC inválido no chunk IDAT.
    """
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), (255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


# ── Banco de dados ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Cria todas as tabelas antes da sessão e as dropa ao final."""
    Base.metadata.create_all(test_engine)
    yield
    Base.metadata.drop_all(test_engine)
    if UPLOAD_DIR.exists():
        shutil.rmtree(UPLOAD_DIR)


@pytest.fixture(autouse=True)
def limpar_rate_limit():
    """Cada teste começa sem tentativas falhas acumuladas (o limitador vive na memória do processo)."""
    from app.rate_limit import limitador
    limitador.reset()
    yield
    limitador.reset()


@pytest.fixture
def db(setup_database):
    """
    Sessão de banco isolada por teste via truncamento de tabelas.

    Usamos truncamento em vez de SAVEPOINT porque SQLite não garante o
    rollback de commits reais dentro de uma transação externa — o que
    quebraria testes que chamam session.commit() (ex.: create_refresh_token).
    A limpeza ocorre em ordem reversa de dependência para respeitar FKs.
    """
    session = Session(test_engine)
    app.dependency_overrides[get_db] = lambda: session
    yield session
    app.dependency_overrides.pop(get_db, None)
    session.close()
    with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def client(db):
    """TestClient do FastAPI com banco de teste já injetado."""
    with TestClient(app) as c:
        yield c


# ── Fixtures de usuários ────────────────────────────────────────────────────────

@pytest.fixture
def user_admin(db):
    u = Usuario(
        nome="Admin Teste",
        email="admin@test.com",
        senha_hash=_SENHA_HASH,
        role="admin",
        mfa_enabled=True,
        mfa_secret=MFA_TEST_SECRET,
        ativo=True,
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def user_gestor(db):
    u = Usuario(
        nome="Gestor Teste",
        email="gestor@test.com",
        senha_hash=_SENHA_HASH,
        role="gestor",
        mfa_enabled=True,
        mfa_secret=MFA_TEST_SECRET,
        ativo=True,
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def user_vistoriador(db):
    u = Usuario(
        nome="Vistoriador Teste",
        email="vistoriador@test.com",
        senha_hash=_SENHA_HASH,
        role="vistoriador",
        mfa_enabled=True,
        mfa_secret=MFA_TEST_SECRET,
        ativo=True,
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def user_locatario(db):
    u = Usuario(
        nome="Locatario Teste",
        email="locatario@test.com",
        senha_hash=_SENHA_HASH,
        role="locatario",
        mfa_enabled=False,
        ativo=True,
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def user_visualizador(db):
    u = Usuario(
        nome="Visualizador Teste",
        email="visualizador@test.com",
        senha_hash=_SENHA_HASH,
        role="visualizador",
        mfa_enabled=False,
        ativo=True,
    )
    db.add(u)
    db.flush()
    return u


# ── Fixtures de tokens de acesso ────────────────────────────────────────────────
# Tokens gerados diretamente (sem passar por login) para evitar dependência
# do fluxo de autenticação nos testes que não são de auth.

@pytest.fixture
def token_admin(user_admin):
    return create_access_token(user_admin.id, user_admin.role)


@pytest.fixture
def token_gestor(user_gestor):
    return create_access_token(user_gestor.id, user_gestor.role)


@pytest.fixture
def token_vistoriador(user_vistoriador):
    return create_access_token(user_vistoriador.id, user_vistoriador.role)


@pytest.fixture
def token_locatario(user_locatario):
    return create_access_token(user_locatario.id, user_locatario.role)


@pytest.fixture
def token_visualizador(user_visualizador):
    return create_access_token(user_visualizador.id, user_visualizador.role)


# ── Fixtures de dados base ──────────────────────────────────────────────────────

@pytest.fixture
def imovel(db):
    """Imóvel disponível com os 4 cômodos padrão já criados."""
    im = Imovel(
        tipo="apartamento",
        titulo="Apto Teste",
        codigo="APT-001",
        status="disponivel",
        garagem=False,
        garagem_vagas=0,
    )
    db.add(im)
    db.flush()
    for nome, tipo in [
        ("Sala", "sala"),
        ("Cozinha", "cozinha"),
        ("Quarto 1", "quarto"),
        ("Banheiro", "banheiro"),
    ]:
        db.add(ImovelComodo(imovel_id=im.id, tipo=tipo, nome=nome, descricao=nome))
    db.flush()
    return im


@pytest.fixture
def contrato(db, imovel, user_locatario):
    """Contrato ativo com 2 agendamentos de vistoria (inicial e encerramento)."""
    imovel.status = "locado"
    ct = Contrato(
        imovel_id=imovel.id,
        locatario_id=user_locatario.id,
        data_inicio=date(2025, 1, 1),
        data_fim=date(2025, 12, 31),
        valor_mensal=1500.00,
        status="ativo",
    )
    db.add(ct)
    db.flush()
    for tipo, dt in [("inicial", date(2025, 1, 1)), ("encerramento", date(2025, 12, 31))]:
        db.add(
            AgendamentoVistoria(
                contrato_id=ct.id,
                tipo=tipo,
                data_agendada=dt,
                observacao=f"Vistoria de {tipo}",
            )
        )
    db.flush()
    return ct


@pytest.fixture
def item_vistoria(db):
    """Item do catálogo de vistoria para uso em checklist_itens."""
    iv = ItemVistoria(nome="Pintura", categoria="Acabamento")
    db.add(iv)
    db.flush()
    return iv


@pytest.fixture
def checklist(db, contrato, user_vistoriador):
    """Checklist inicial em preenchimento, vinculado ao contrato e vistoriador de teste."""
    ck = Checklist(
        contrato_id=contrato.id,
        vistoriador_id=user_vistoriador.id,
        tipo="inicial",
        status="em_preenchimento",
        data_vistoria=date.today(),
    )
    db.add(ck)
    db.flush()
    return ck
