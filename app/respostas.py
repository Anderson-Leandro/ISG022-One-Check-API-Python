"""Respostas documentadas no OpenAPI (DEBT-002).

Os serializadores de app/serializers.py montam os dicionários; estes modelos só os descrevem, pelo
`responses` de cada rota principal (`documentar`). Nada é filtrado nem validado na resposta, então o
que a API devolve não muda. tests/integration/test_openapi_respostas.py confere, rota a rota, que a
resposta real bate com o modelo (sem campo a mais nem a menos), para a documentação não se separar
do código.

Nomes: o perfil do usuário é sempre `role` (admin, gestor, vistoriador ou locatario), nas respostas,
nos corpos e nos filtros. "Perfil" só aparece em mensagens de texto. O MFA tem três campos, cada um com
um sentido (ver UsuarioResposta).
"""

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class _Modelo(BaseModel):
    # forbid: o teste de contrato recusa um campo da resposta que não esteja documentado
    model_config = ConfigDict(extra="forbid")


class PaginacaoResposta(_Modelo):
    total: int
    pagina: int
    itensPorPagina: int


class Envelope(_Modelo, Generic[T]):
    """O envelope de toda resposta de sucesso (ADR-0003)."""

    sucesso: Literal[True] = Field(description="Sempre true numa resposta 2xx")
    dados: T
    paginacao: PaginacaoResposta | None = Field(None, description="Só nas listagens paginadas")


class ErroResposta(_Modelo):
    """O envelope de todo erro da API: o status HTTP acompanha o resultado (ADR-0003, DEBT-020)."""

    sucesso: Literal[False] = Field(description="Sempre false")
    erro: str = Field(description="Mensagem para mostrar ao usuário")
    erros: dict[str, Any] | list[str] | None = Field(
        None, description="Mensagem por campo, nos 422 (o nome aninhado vem com ponto: endereco.rua)"
    )


# SEC-029: o mesmo campo no perfil e no login
_SENHA_EXPIRADA = Field(
    False,
    description="A senha não atende à política atual: até trocá-la (PUT /usuarios/me/senha), as outras rotas "
    "respondem 403 (SEC-029)",
)


class UsuarioResposta(_Modelo):
    id: str
    nome: str
    email: str
    role: str = Field(description="Perfil de acesso: admin, gestor, vistoriador ou locatario")
    cpf: str | None = Field(
        None, description="Completo para o próprio usuário e no detalhe de admin e gestor; mascarado nas listas"
    )
    mfa_enabled: bool = Field(description="O MFA está ligado (exigido) para a conta")
    mfa_configurado: bool = Field(description="A conta já tem um autenticador configurado")
    mfa_ativo: bool = Field(
        description="O login pede o código: MFA ligado e autenticador configurado (mfa_enabled e mfa_configurado)"
    )
    senha_expirada: bool = _SENHA_EXPIRADA
    created_at: str | None = None


class EnderecoResposta(_Modelo):
    rua: str | None = None
    logradouro: str | None = Field(None, description="O mesmo valor de `rua`, mantido por compatibilidade")
    numero: str | None = None
    complemento: str | None = None
    bloco: str | None = None
    andar: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    estado: str | None = None
    cep: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class ImovelResposta(_Modelo):
    id: str
    codigo: str | None = None
    titulo: str | None = None
    tipo: str
    tamanho: str | None = None
    garagem: bool
    garagem_vagas: int
    status: str
    observacoes: str | None = None
    ativo: bool
    created_at: str | None = None
    endereco: EnderecoResposta | None = Field(None, description="Só no detalhe e na criação")


class ComodoResposta(_Modelo):
    id: str
    imovel_id: str
    tipo: str
    descricao: str | None = None
    nome: str | None = None


class ContratoResposta(_Modelo):
    id: str
    imovel_id: str
    locatario_id: str
    data_inicio: str
    data_fim: str
    valor_mensal: float | None = None
    status: str
    created_at: str | None = None


class AgendamentoResposta(_Modelo):
    id: str
    contrato_id: str
    tipo: str = Field(description="inicial ou encerramento")
    data_agendada: str | None = None
    observacao: str | None = Field(None, description="Nota interna da equipe: não vai na resposta para o locatário")
    created_at: str | None = None


class FotoResposta(_Modelo):
    id: str
    url: str | None = None


class ItemChecklistResposta(_Modelo):
    id: str
    checklist_id: str
    comodo_id: str | None = None
    item_vistoria_id: str | None = None
    estado: str | None = None
    observacao: str | None = None
    fotos: list[FotoResposta]


class AceiteResposta(_Modelo):
    id: str
    checklist_id: str
    locatario_id: str
    status: str
    motivo_rejeicao: str | None = None
    created_at: str | None = None


class ChecklistResposta(_Modelo):
    id: str
    contrato_id: str
    vistoriador_id: str | None = None
    tipo: str
    status: str
    data_vistoria: str | None = None
    created_at: str | None = None
    aceite: AceiteResposta | None = None
    itens: list[ItemChecklistResposta] | None = Field(None, description="Só no detalhe")
    comodos: list[ComodoResposta] | None = Field(None, description="Só no detalhe")


class AtualizacaoProblemaResposta(_Modelo):
    id: str
    problema_id: str
    autor_id: str | None = None
    descricao: str
    foto_url: str | None = None
    created_at: str | None = None


class ProblemaResposta(_Modelo):
    id: str
    contrato_id: str
    comodo_id: str | None = None
    titulo: str
    descricao: str | None = None
    foto_url: str | None = None
    prioridade: str
    status: str
    created_at: str | None = None
    atualizacoes: list[AtualizacaoProblemaResposta]


class UsuarioLoginResposta(_Modelo):
    """O usuário no login e no MFA: só a identificação e o perfil (os dados completos vêm de /usuarios/me)."""

    id: str
    nome: str
    email: str
    role: str = Field(description="Perfil de acesso: admin, gestor, vistoriador ou locatario")
    senha_expirada: bool = _SENHA_EXPIRADA


class LoginResposta(_Modelo):
    """Uma de três formas: tokens (login completo), mfa_required ou mfa_setup_required, com o temp_token."""

    access_token: str | None = None
    refresh_token: str | None = None
    usuario: UsuarioLoginResposta | None = None
    mfa_required: bool | None = Field(None, description="Falta o código: POST /auth/mfa/verify com o temp_token")
    mfa_setup_required: bool | None = Field(
        None, description="Falta configurar o autenticador: GET /auth/mfa/setup-login com o temp_token"
    )
    temp_token: str | None = Field(None, description="Vale 10 minutos, só para o próximo passo do login")
    mfa_token: str | None = Field(None, description="O mesmo valor de `temp_token`, mantido por compatibilidade")


class TokensResposta(_Modelo):
    access_token: str
    refresh_token: str = Field(description="Novo a cada renovação: o anterior deixa de valer")


_ERROS = {
    400: "Regra da rota violada, como datas incoerentes",
    401: "Sem token, token inválido ou sessão encerrada, ou credenciais inválidas no login",
    403: "O perfil ou o dono do registro não permite a operação",
    404: "Registro não encontrado",
    409: "Conflito com o estado atual, como um registro em uso ou duplicado",
    422: "Dados inválidos, com a mensagem por campo em `erros` (regra da rota ou corpo fora do schema)",
    429: "Tentativas demais: espere o tempo do cabeçalho Retry-After",
}


def documentar(modelo: type[BaseModel], *, erros: tuple[int, ...], lista: bool = False, status: int = 200) -> dict:
    """`responses` de uma rota: o envelope com `dados` do modelo (ou lista dele) e os erros que ela devolve.

    Todo erro usa o envelope `ErroResposta` (DEBT-020)."""
    dados = list[modelo] if lista else modelo
    respostas: dict[int | str, dict] = {status: {"model": Envelope[dados], "description": "Sucesso"}}
    for codigo in erros:
        respostas[codigo] = {"model": ErroResposta, "description": _ERROS[codigo]}
    return respostas
