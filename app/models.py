import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="visualizador")
    cpf: Mapped[str | None] = mapped_column(String(14))
    mfa_secret: Mapped[str | None] = mapped_column(String(64))
    # Segredo gerado no setup; só vira mfa_secret depois que um código válido confirmar
    mfa_secret_pendente: Mapped[str | None] = mapped_column(String(64))
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="usuario")


class RefreshToken(Base):
    __tablename__ = "auth_refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    usuario_id: Mapped[str] = mapped_column(String(36), ForeignKey("usuarios.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    usuario: Mapped[Usuario] = relationship(back_populates="refresh_tokens")


class Imovel(Base):
    __tablename__ = "imoveis"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    codigo: Mapped[str | None] = mapped_column(String(50))
    titulo: Mapped[str | None] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(100), nullable=False)
    tamanho: Mapped[str | None] = mapped_column(String(50))
    garagem: Mapped[bool] = mapped_column(Boolean, default=False)
    garagem_vagas: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(50), default="disponivel")
    observacoes: Mapped[str | None] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    endereco: Mapped["Endereco | None"] = relationship(back_populates="imovel", uselist=False)
    comodos: Mapped[list["ImovelComodo"]] = relationship(back_populates="imovel")


class Endereco(Base):
    __tablename__ = "enderecos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    imovel_id: Mapped[str] = mapped_column(String(36), ForeignKey("imoveis.id"), unique=True)
    rua: Mapped[str] = mapped_column(String(200), nullable=False)
    numero: Mapped[str | None] = mapped_column(String(20))
    complemento: Mapped[str | None] = mapped_column(String(100))
    bloco: Mapped[str | None] = mapped_column(String(50))
    andar: Mapped[str | None] = mapped_column(String(50))
    bairro: Mapped[str | None] = mapped_column(String(100))
    cidade: Mapped[str] = mapped_column(String(100), nullable=False)
    estado: Mapped[str] = mapped_column(String(2), nullable=False)
    cep: Mapped[str | None] = mapped_column(String(10))
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    imovel: Mapped[Imovel] = relationship(back_populates="endereco")


class ImovelComodo(Base):
    __tablename__ = "imovel_comodos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    imovel_id: Mapped[str] = mapped_column(String(36), ForeignKey("imoveis.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(100), nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(200))
    nome: Mapped[str | None] = mapped_column(String(100))

    imovel: Mapped[Imovel] = relationship(back_populates="comodos")


class Contrato(Base):
    __tablename__ = "contratos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    imovel_id: Mapped[str] = mapped_column(String(36), ForeignKey("imoveis.id"), nullable=False)
    locatario_id: Mapped[str] = mapped_column(String(36), ForeignKey("usuarios.id"), nullable=False)
    data_inicio: Mapped[Date] = mapped_column(Date, nullable=False)
    data_fim: Mapped[Date] = mapped_column(Date, nullable=False)
    valor_mensal: Mapped[float | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(50), default="ativo")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    agendamentos: Mapped[list["AgendamentoVistoria"]] = relationship(back_populates="contrato")
    checklists: Mapped[list["Checklist"]] = relationship(back_populates="contrato")
    problemas: Mapped[list["Problema"]] = relationship(back_populates="contrato")


class AgendamentoVistoria(Base):
    __tablename__ = "agendamentos_vistoria"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    contrato_id: Mapped[str] = mapped_column(String(36), ForeignKey("contratos.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    data_agendada: Mapped[datetime | None] = mapped_column(DateTime)
    observacao: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    contrato: Mapped[Contrato] = relationship(back_populates="agendamentos")


class Checklist(Base):
    __tablename__ = "checklists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    contrato_id: Mapped[str] = mapped_column(String(36), ForeignKey("contratos.id"), nullable=False)
    vistoriador_id: Mapped[str] = mapped_column(String(36), ForeignKey("usuarios.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="em_preenchimento")
    data_vistoria: Mapped[Date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    contrato: Mapped[Contrato] = relationship(back_populates="checklists")
    itens: Mapped[list["ChecklistItem"]] = relationship(back_populates="checklist", cascade="all, delete-orphan")
    aceite: Mapped["AceiteChecklist | None"] = relationship(back_populates="checklist", uselist=False, cascade="all, delete-orphan")


class AceiteChecklist(Base):
    __tablename__ = "aceite_checklists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    checklist_id: Mapped[str] = mapped_column(String(36), ForeignKey("checklists.id"), unique=True, nullable=False)
    locatario_id: Mapped[str] = mapped_column(String(36), ForeignKey("usuarios.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    motivo_rejeicao: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    checklist: Mapped[Checklist] = relationship(back_populates="aceite")
    locatario: Mapped[Usuario] = relationship()


class ChecklistItem(Base):
    __tablename__ = "checklist_itens"
    __table_args__ = (
        UniqueConstraint("checklist_id", "comodo_id", "item_vistoria_id", name="uq_checklist_comodo_item"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    checklist_id: Mapped[str] = mapped_column(String(36), ForeignKey("checklists.id"), nullable=False)
    comodo_id: Mapped[str] = mapped_column(String(36), ForeignKey("imovel_comodos.id"), nullable=False)
    item_vistoria_id: Mapped[str] = mapped_column(String(36), ForeignKey("itens_vistoria.id"), nullable=False)
    estado: Mapped[str | None] = mapped_column(String(20))
    observacao: Mapped[str | None] = mapped_column(Text)

    checklist: Mapped[Checklist] = relationship(back_populates="itens")
    fotos: Mapped[list["ChecklistItemFoto"]] = relationship(back_populates="item", cascade="all, delete-orphan")


class ChecklistItemFoto(Base):
    __tablename__ = "checklist_item_fotos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("checklist_itens.id"), nullable=False)
    arquivo: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    item: Mapped[ChecklistItem] = relationship(back_populates="fotos")


class ItemVistoria(Base):
    __tablename__ = "itens_vistoria"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    categoria: Mapped[str | None] = mapped_column(String(100))


class Problema(Base):
    __tablename__ = "problemas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    contrato_id: Mapped[str] = mapped_column(String(36), ForeignKey("contratos.id"), nullable=False)
    comodo_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("imovel_comodos.id"), nullable=True)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    foto_url: Mapped[str | None] = mapped_column(String(500))
    prioridade: Mapped[str] = mapped_column(String(50), default="normal")
    status: Mapped[str] = mapped_column(String(50), default="aberto")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    contrato: Mapped[Contrato] = relationship(back_populates="problemas")
    comodo: Mapped["ImovelComodo | None"] = relationship()
    atualizacoes: Mapped[list["AtualizacaoProblema"]] = relationship(back_populates="problema", cascade="all, delete-orphan")


class AtualizacaoProblema(Base):
    __tablename__ = "atualizacoes_problema"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    problema_id: Mapped[str] = mapped_column(String(36), ForeignKey("problemas.id"), nullable=False)
    autor_id: Mapped[str] = mapped_column(String(36), ForeignKey("usuarios.id"), nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    foto_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    problema: Mapped[Problema] = relationship(back_populates="atualizacoes")
    autor: Mapped[Usuario] = relationship()


class LogOperacao(Base):
    __tablename__ = "log_operacao"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    usuario_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("usuarios.id"))
    acao: Mapped[str] = mapped_column(String(100), nullable=False)
    entidade: Mapped[str | None] = mapped_column(String(100))
    entidade_id: Mapped[str | None] = mapped_column(String(36))
    detalhes: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
