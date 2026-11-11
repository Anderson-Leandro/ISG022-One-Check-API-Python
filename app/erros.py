"""Todo erro no envelope {sucesso: false, erro, erros} (DEBT-020, ADR-0003).

As regras de negócio já respondiam assim. Faltavam os erros levantados pelo framework: o 401 de token e o
403 de perfil das dependências (HTTPException), o 404 e o 405 do roteador, o 422 de corpo, consulta ou
caminho fora do schema (RequestValidationError) e o 500 de exceção não tratada. Os handlers abaixo mantêm o
status e os cabeçalhos da exceção (Retry-After do 429, Allow do 405) e trocam só o corpo. O 500 não expõe a
exceção: a mensagem é genérica, e o detalhe fica no log do servidor.

`erros_no_openapi` faz o OpenAPI gerado declarar o mesmo envelope (ErroResposta) em toda resposta 4xx e
5xx, inclusive no 422 que o FastAPI acrescenta sozinho (HTTPValidationError).
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from app.respostas import ErroResposta

_ORIGENS = {"body", "query", "path", "header", "cookie"}
_ERRO = {"$ref": "#/components/schemas/ErroResposta"}
# Prefixos que o Pydantic põe nas mensagens dos validadores próprios (como a política de senha)
_PREFIXOS = ("Value error, ", "Assertion failed, ")
_SEM_CORPO = {204, 304}


def corpo_de_erro(erro: str, erros: dict | list | None = None) -> dict:
    return {"sucesso": False, "erro": erro, "erros": erros}


def _origem_e_campo(erro: dict) -> tuple[str, str]:
    """Origem e nome do campo de um erro do Pydantic: ('body', 'endereco', 'rua') vira ('body', 'endereco.rua')."""
    loc = [str(p) for p in erro.get("loc", ())]
    origem = loc.pop(0) if loc and loc[0] in _ORIGENS else "body"
    if not loc or erro.get("type") == "json_invalid":
        return origem, "corpo"
    return origem, ".".join(loc)


def _mensagem(erro: dict) -> str:
    msg = str(erro.get("msg", "Valor inválido"))
    for prefixo in _PREFIXOS:
        msg = msg.removeprefix(prefixo)
    return msg


async def erro_http(_: Request, exc: StarletteHTTPException) -> Response:
    headers = getattr(exc, "headers", None)
    if exc.status_code in _SEM_CORPO:
        return Response(status_code=exc.status_code, headers=headers)
    detalhe = exc.detail
    if isinstance(detalhe, str) and detalhe:
        corpo = corpo_de_erro(detalhe)
    else:
        corpo = corpo_de_erro("Erro na requisição", detalhe if isinstance(detalhe, (dict, list)) else None)
    return JSONResponse(corpo, status_code=exc.status_code, headers=headers)


async def erro_de_validacao(_: Request, exc: RequestValidationError) -> JSONResponse:
    erros: dict[str, str] = {}
    origens: dict[str, str] = {}
    for item in exc.errors():
        origem, campo = _origem_e_campo(item)
        # o mesmo nome em origens diferentes (consulta e corpo) não se sobrepõe: o segundo leva a origem
        if campo in origens and origens[campo] != origem:
            campo = f"{origem}.{campo}"
        origens.setdefault(campo, origem)
        erros.setdefault(campo, _mensagem(item))
    return JSONResponse(corpo_de_erro(next(iter(erros.values()), "Dados inválidos"), erros), status_code=422)


async def erro_interno(_: Request, exc: Exception) -> JSONResponse:
    logging.getLogger(__name__).exception("Erro não tratado: %s", type(exc).__name__)
    return JSONResponse(corpo_de_erro("Erro interno. Tente novamente mais tarde."), status_code=500)


def registrar(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, erro_http)
    app.add_exception_handler(RequestValidationError, erro_de_validacao)
    app.add_exception_handler(Exception, erro_interno)


def erros_no_openapi(app: FastAPI) -> None:
    """Toda resposta 4xx e 5xx do OpenAPI gerado aponta para ErroResposta (feito uma vez, no schema em cache)."""
    gerar = app.openapi
    processado = None

    def openapi():
        nonlocal processado
        schema = gerar()
        if schema is processado:
            return schema
        componentes = schema.setdefault("components", {}).setdefault("schemas", {})
        if "ErroResposta" not in componentes:
            componentes["ErroResposta"] = ErroResposta.model_json_schema()
        for operacoes in schema.get("paths", {}).values():
            for operacao in operacoes.values():
                for codigo, resposta in operacao.get("responses", {}).items():
                    if str(codigo)[:1] in "45":
                        resposta["content"] = {"application/json": {"schema": dict(_ERRO)}}
        for antigo in ("HTTPValidationError", "ValidationError"):
            componentes.pop(antigo, None)
        processado = schema
        return schema

    app.openapi = openapi
