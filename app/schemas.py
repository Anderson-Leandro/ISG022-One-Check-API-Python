from datetime import date, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Paginacao(BaseModel):
    total: int
    pagina: int
    itensPorPagina: int


class ApiResponse(BaseModel, Generic[T]):
    sucesso: bool = True
    dados: T | None = None
    erro: str | None = None
    erros: dict[str, Any] | list[str] | None = None
    paginacao: Paginacao | None = None


def ok(data: Any, paginacao: Paginacao | dict | None = None) -> dict:
    out: dict[str, Any] = {"sucesso": True, "dados": data}
    if paginacao:
        out["paginacao"] = paginacao.model_dump() if hasattr(paginacao, "model_dump") else paginacao
    return out


def fail(msg: str, erros: Any = None) -> dict:
    out: dict[str, Any] = {"sucesso": False, "erro": msg}
    if erros is not None:
        out["erros"] = erros
    return out


# --- Auth ---

class LoginRequest(BaseModel):
    email: str
    senha: str


class MfaVerifyRequest(BaseModel):
    temp_token: str
    codigo: str


class MfaEnableRequest(BaseModel):
    secret: str = Field(min_length=16, max_length=64)
    codigo: str = Field(min_length=6, max_length=6)


class MfaActivateRequest(BaseModel):
    codigo: str = Field(min_length=6, max_length=6)


class MfaActivateLoginRequest(BaseModel):
    temp_token: str
    codigo: str = Field(min_length=6, max_length=6)


class MfaDisableRequest(BaseModel):
    usuario_id: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UsuarioOut(BaseModel):
    id: str
    nome: str
    email: str
    role: str

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    mfa_required: bool | None = None
    mfa_setup_required: bool | None = None
    temp_token: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    usuario: UsuarioOut | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None


# --- Usuarios ---

class UsuarioCreate(BaseModel):
    nome: str
    email: str
    senha: str = Field(min_length=6)
    role: str
    cpf: str | None = None


class UsuarioUpdateMe(BaseModel):
    nome: str | None = None
    senha_atual: str | None = None
    senha_nova: str | None = Field(default=None, min_length=6)


class AlterarSenhaRequest(BaseModel):
    senha_atual: str
    nova_senha: str = Field(min_length=6)


class UsuarioUpdate(BaseModel):
    nome: str | None = None
    email: str | None = None
    role: str | None = None
    senha: str | None = Field(default=None, min_length=6)
    mfa_enabled: bool | None = None


# --- Enderecos & Imoveis ---

class EnderecoCreate(BaseModel):
    rua: str
    numero: str | None = None
    complemento: str | None = None
    bloco: str | None = None
    andar: str | None = None
    bairro: str | None = None
    cidade: str
    estado: str
    cep: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class ImovelCreate(BaseModel):
    codigo: str | None = None
    titulo: str | None = None
    tipo: str
    tamanho: str | None = None
    garagem: bool = False
    garagem_vagas: int = 0
    status: str = "disponivel"
    observacoes: str | None = None
    endereco: EnderecoCreate | None = None


class ImovelUpdate(BaseModel):
    codigo: str | None = None
    titulo: str | None = None
    tipo: str | None = None
    tamanho: str | None = None
    garagem: bool | None = None
    garagem_vagas: int | None = None
    status: str | None = None
    observacoes: str | None = None
    endereco: EnderecoCreate | None = None


# --- Comodos ---

class ComodoCreate(BaseModel):
    tipo: str
    descricao: str | None = None


class ComodoUpdate(BaseModel):
    tipo: str | None = None
    descricao: str | None = None


class ComodoOut(BaseModel):
    id: str
    imovel_id: str
    tipo: str
    descricao: str | None = None
    nome: str | None = None

    model_config = {"from_attributes": True}


class ImovelOut(BaseModel):
    id: str
    codigo: str | None = None
    titulo: str | None = None
    tipo: str
    tamanho: str | None = None
    garagem: bool
    garagem_vagas: int = 0
    status: str
    observacoes: str | None = None
    ativo: bool = True
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class EnderecoOut(BaseModel):
    rua: str
    logradouro: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bloco: str | None = None
    andar: str | None = None
    bairro: str | None = None
    cidade: str
    estado: str
    cep: str | None = None
    latitude: float | None = None
    longitude: float | None = None


# --- Contratos ---

class ContratoCreate(BaseModel):
    imovel_id: str
    locatario_id: str
    data_inicio: date
    data_fim: date
    valor_mensal: float | None = None


class ContratoOut(BaseModel):
    id: str
    imovel_id: str
    locatario_id: str
    data_inicio: date
    data_fim: date
    valor_mensal: float | None = None
    status: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgendamentoCreate(BaseModel):
    tipo: str
    data_agendada: datetime | date | str
    observacao: str | None = None


class AgendamentoUpdate(BaseModel):
    tipo: str | None = None
    data_agendada: datetime | date | str | None = None
    observacao: str | None = None


class AgendamentoOut(BaseModel):
    id: str
    contrato_id: str
    tipo: str
    data_agendada: datetime | date | None = None
    observacao: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Checklists ---

class ChecklistCreate(BaseModel):
    tipo: str
    data_vistoria: date | None = None
    vistoriador_id: str


class FotoOut(BaseModel):
    id: str
    url: str


class AceiteChecklistOut(BaseModel):
    id: str
    checklist_id: str
    locatario_id: str
    status: str
    motivo_rejeicao: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AceiteChecklistRequest(BaseModel):
    motivo_rejeicao: str | None = None
    motivo: str | None = None


class RejeitarChecklistRequest(BaseModel):
    motivo: str | None = None
    motivo_rejeicao: str | None = None


class ChecklistItemOut(BaseModel):
    id: str
    checklist_id: str
    comodo_id: str
    item_vistoria_id: str
    estado: str | None = None
    observacao: str | None = None
    fotos: list[FotoOut] = []


class ChecklistOut(BaseModel):
    id: str
    contrato_id: str
    vistoriador_id: str
    tipo: str
    status: str
    data_vistoria: date | None = None
    created_at: datetime | None = None
    itens: list[ChecklistItemOut] | None = None
    comodos: list[ComodoOut] | None = None
    aceite: AceiteChecklistOut | None = None


class AddChecklistItemRequest(BaseModel):
    comodo_id: str
    item_vistoria_id: str
    estado: str
    observacao: str | None = None


class ItemUpdateRequest(BaseModel):
    estado: str | None = None
    observacao: str | None = None


class FotoUploadResponse(BaseModel):
    id: str
    url: str


class ItemVistoriaOut(BaseModel):
    id: str
    nome: str
    categoria: str | None = None

    model_config = {"from_attributes": True}


# --- Problemas ---

class AtualizacaoProblemaCreate(BaseModel):
    descricao: str
    foto_url: str | None = None


class AtualizacaoProblemaOut(BaseModel):
    id: str
    problema_id: str
    autor_id: str
    descricao: str
    foto_url: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ProblemaCreate(BaseModel):
    titulo: str
    descricao: str | None = None
    comodo_id: str | None = None
    foto_url: str | None = None
    prioridade: str = "normal"
    status: str = "aberto"


class ProblemaOut(BaseModel):
    id: str
    contrato_id: str
    comodo_id: str | None = None
    titulo: str
    descricao: str | None = None
    foto_url: str | None = None
    prioridade: str
    status: str
    created_at: datetime | None = None
    atualizacoes: list[AtualizacaoProblemaOut] = []

    model_config = {"from_attributes": True}


# --- Dashboard / Logs ---

class DashboardOut(BaseModel):
    imoveis_locados: int
    checklists_pendentes: int
    problemas_abertos: int
    vistorias_agendadas: int


class LogOut(BaseModel):
    id: str
    usuario_id: str | None = None
    acao: str
    entidade: str | None = None
    entidade_id: str | None = None
    detalhes: str | None = None
    payload: Any | None = None
    ip: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
