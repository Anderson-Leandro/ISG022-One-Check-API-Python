from datetime import date, datetime
from typing import Annotated, Any, Generic, TypeVar

from fastapi.responses import JSONResponse
from pydantic import AfterValidator, BaseModel, Field, WithJsonSchema

from app.cpf import validar_cpf
from app.senhas import validar_senha

T = TypeVar("T")

# Senha nova (criação e troca). O login aceita a senha já cadastrada, mesmo fora da política
SenhaNova = Annotated[str, AfterValidator(validar_senha)]
Cpf = Annotated[str | None, AfterValidator(validar_cpf)]
# Só documenta os valores no OpenAPI; a validação fica nas rotas, com a mensagem de campo (ADR-0012)
TIPOS_AGENDAMENTO = ("inicial", "encerramento")
TipoAgendamento = Annotated[str, Field(json_schema_extra={"enum": list(TIPOS_AGENDAMENTO)})]
# Problemas (DEBT-001): os valores aceitos, usados pelas rotas e documentados no OpenAPI da mesma forma
PRIORIDADES_PROBLEMA = ("normal", "alta", "urgente")
STATUS_PROBLEMA = ("aberto", "em_andamento", "em_analise", "resolvido", "fechado")
# Status finais: o locatário não comenta mais (ADR-0012)
STATUS_PROBLEMA_ENCERRADOS = frozenset({"resolvido", "fechado"})
PrioridadeProblema = Annotated[str, Field(json_schema_extra={"enum": list(PRIORIDADES_PROBLEMA)})]
StatusProblema = Annotated[str, Field(json_schema_extra={"enum": list(STATUS_PROBLEMA)})]
# Na criação, o problema nasce aberto: o andamento muda só por PATCH /problemas/{id}/status
StatusInicialProblema = Annotated[str, Field(json_schema_extra={"enum": ["aberto"]})]
# Arquivo de um envio multipart, como o OpenAPI o descreve
Arquivo = Annotated[bytes | None, WithJsonSchema({"type": "string", "format": "binary"})]


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


def fail(msg: str, erros: Any = None, status_code: int = 400) -> JSONResponse:
    """Resposta de erro no envelope padrão, sempre com status de erro (ADR-0003).

    Sem status explícito, o padrão é 400: um erro nunca sai como 2xx (fail secure).
    """
    if status_code < 400:
        raise ValueError(f"fail() exige status de erro (>= 400), recebeu {status_code}")
    out: dict[str, Any] = {"sucesso": False, "erro": msg}
    if erros is not None:
        out["erros"] = erros
    return JSONResponse(status_code=status_code, content=out)


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
    codigo_atual: str | None = None


class MfaActivateRequest(BaseModel):
    codigo: str = Field(min_length=6, max_length=6)
    codigo_atual: str | None = None


class MfaActivateLoginRequest(BaseModel):
    temp_token: str
    codigo: str = Field(min_length=6, max_length=6)


class MfaDisableRequest(BaseModel):
    usuario_id: str


class MfaDisableSelfRequest(BaseModel):
    senha: str
    codigo: str | None = None


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
    senha: SenhaNova
    role: str
    cpf: Cpf = None


class UsuarioUpdateMe(BaseModel):
    nome: str | None = None
    senha_atual: str | None = None
    senha_nova: SenhaNova | None = None


class AlterarSenhaRequest(BaseModel):
    senha_atual: str
    nova_senha: SenhaNova


class UsuarioUpdate(BaseModel):
    nome: str | None = None
    email: str | None = None
    role: str | None = None
    senha: SenhaNova | None = None
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
    tipo: TipoAgendamento
    data_agendada: datetime | date | str
    observacao: str | None = None


class AgendamentoUpdate(BaseModel):
    tipo: TipoAgendamento | None = None
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


class _AtualizacaoProblemaBase(BaseModel):
    descricao: str = Field(
        description="Pelo menos 5 caracteres, sem contar os espaços nas pontas",
        json_schema_extra={"minLength": 5},
    )


class AtualizacaoProblemaCreate(_AtualizacaoProblemaBase):
    foto_url: str | None = Field(None, description="Uma foto já enviada pelo upload da API")


class AtualizacaoProblemaForm(_AtualizacaoProblemaBase):
    """O mesmo corpo em multipart/form-data, com a foto no próprio envio."""

    foto: Arquivo = Field(None, description="JPEG, PNG ou WebP")


class ProblemaStatusUpdate(BaseModel):
    status: StatusProblema


class AtualizacaoProblemaOut(BaseModel):
    id: str
    problema_id: str
    autor_id: str
    descricao: str
    foto_url: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class _ProblemaBase(BaseModel):
    titulo: str
    descricao: str | None = None
    comodo_id: str | None = None
    prioridade: PrioridadeProblema = "normal"
    status: StatusInicialProblema = "aberto"


class ProblemaCreate(_ProblemaBase):
    foto_url: str | None = Field(None, description="Uma foto já enviada pelo upload da API")


class ProblemaForm(_ProblemaBase):
    """O mesmo corpo em multipart/form-data, com a foto no próprio envio."""

    foto: Arquivo = Field(None, description="JPEG, PNG ou WebP")


def corpo_no_openapi(json: type[BaseModel], multipart: type[BaseModel] | None = None) -> dict:
    """openapi_extra com o requestBody da rota, a partir dos modelos.

    Para as rotas que leem o corpo à mão (JSON ou multipart, e só depois da autorização): o OpenAPI mostra o
    corpo, e a leitura e as mensagens de erro continuam as da rota."""

    def esquema(modelo: type[BaseModel]) -> dict:
        schema = modelo.model_json_schema()
        # Um modelo aninhado geraria $defs com referências que não resolvem dentro do OpenAPI da rota
        if "$defs" in schema:
            raise ValueError(f"{modelo.__name__}: modelo aninhado não cabe no corpo documentado à mão")
        return schema

    conteudo = {"application/json": {"schema": esquema(json)}}
    if multipart:
        conteudo["multipart/form-data"] = {"schema": esquema(multipart)}
    return {"requestBody": {"required": True, "content": conteudo}}


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
