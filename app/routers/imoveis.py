from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auditoria import campos_alterados
from app.database import get_db
from app.deps import (
    assert_acesso_imovel,
    assert_acesso_problemas,
    get_current_user,
    negar_perfil_desconhecido,
    require_roles,
)
from app.geocoding import buscar_coordenadas
from app.models import Checklist, ChecklistItem, Contrato, Endereco, Imovel, ImovelComodo, Problema, Usuario
from app.schemas import (
    ComodoCreate,
    ComodoUpdate,
    EnderecoCreate,
    ImovelCreate,
    ImovelUpdate,
    fail,
    ok,
)
from app.serializers import (
    ensure_default_comodos,
    log_operacao,
    paginate,
    serialize_checklist,
    serialize_comodo,
    serialize_contrato,
    serialize_endereco,
    serialize_imovel,
    serialize_problema,
)

router = APIRouter(prefix="/imoveis", tags=["imoveis"])


_COMODO_EM_USO = "Este cômodo é usado em vistorias ou problemas e não pode ser excluído"


def _comodo_em_uso(db: Session, comodo_id: str) -> bool:
    """Referências ao cômodo em itens de checklist ou problemas, inclusive em registros excluídos (ADR-0008).

    Lê as tabelas do Core, por fora do filtro de exclusão lógica do ORM: a chave estrangeira vale também para
    o registro excluído, que continua no banco (BUG-001).
    """
    itens, problemas = ChecklistItem.__table__, Problema.__table__
    conn = db.connection()
    return any(
        conn.execute(select(t.c.id).where(t.c.comodo_id == comodo_id).limit(1)).first() is not None
        for t in (itens, problemas)
    )


def _apply_endereco(end: Endereco, body: EnderecoCreate, *, is_new: bool) -> None:
    end.rua = body.rua
    end.numero = body.numero
    end.complemento = body.complemento
    end.bloco = body.bloco
    end.andar = body.andar
    end.bairro = body.bairro
    end.cidade = body.cidade
    end.estado = body.estado.upper()
    end.cep = body.cep

    lat = body.latitude
    lon = body.longitude

    # Geocoding automático se coordenadas não foram fornecidas
    if lat is None or lon is None:
        coords = buscar_coordenadas(f"{body.rua}, {body.numero or ''}, {body.cidade}, {body.estado}, Brasil")
        if coords:
            lat = lat if lat is not None else coords.get("latitude")
            lon = lon if lon is not None else coords.get("longitude")

    if lat is not None or is_new:
        end.latitude = lat
    if lon is not None or is_new:
        end.longitude = lon


@router.get("")
def list_imoveis(
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
    status: str | None = None,
    com_endereco: bool = Query(False, description="Inclui endereço com latitude/longitude"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    negar_perfil_desconhecido(user)
    q = db.query(Imovel).filter(Imovel.ativo == True)
    if com_endereco:
        q = q.options(joinedload(Imovel.endereco))
    if user.role == "locatario":
        sub = db.query(Contrato.imovel_id).filter(Contrato.locatario_id == user.id, Contrato.status == "ativo")
        q = q.filter(Imovel.id.in_(sub))
    elif user.role == "vistoriador":
        sub = (
            db.query(Contrato.imovel_id)
            .join(Checklist, Checklist.contrato_id == Contrato.id)
            .filter(Checklist.vistoriador_id == user.id)
            .distinct()
        )
        q = q.filter(Imovel.id.in_(sub))
    if status:
        q = q.filter(Imovel.status == status)
    q = q.order_by(Imovel.created_at.desc())
    items, pag = paginate(q, pagina, por_pagina)
    return ok([serialize_imovel(i, include_endereco=com_endereco) for i in items], pag)


@router.post("")
def create_imovel(
    body: ImovelCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_roles("admin", "gestor")),
):
    im = Imovel(
        codigo=body.codigo,
        titulo=body.titulo,
        tipo=body.tipo,
        tamanho=body.tamanho,
        garagem=body.garagem,
        garagem_vagas=body.garagem_vagas,
        status=body.status,
        observacoes=body.observacoes,
        ativo=True,
    )
    db.add(im)
    db.flush()

    if body.endereco:
        end = Endereco(imovel_id=im.id, ativo=True)
        _apply_endereco(end, body.endereco, is_new=True)
        db.add(end)

    db.commit()
    db.refresh(im)
    ensure_default_comodos(db, im.id)
    log_operacao(db, user.id, "create", "imovel", im.id)
    return ok(serialize_imovel(im, include_endereco=bool(body.endereco)))


@router.get("/{imovel_id}")
def get_imovel(
    imovel_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    negar_perfil_desconhecido(user)
    im = (
        db.query(Imovel)
        .options(joinedload(Imovel.endereco))
        .filter(Imovel.id == imovel_id, Imovel.ativo == True)
        .first()
    )
    if not im:
        return fail("Imóvel não encontrado", status_code=404)
    assert_acesso_imovel(db, imovel_id, user)
    return ok(serialize_imovel(im, include_endereco=True))


@router.get("/{imovel_id}/historico")
def historico_imovel(
    imovel_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Contratos, vistorias e problemas do imóvel em ordem cronológica de registro (US-017).

    Cada perfil vê só o que já acessa pelas listagens (GET /contratos, GET /contratos/{id}/checklists e
    /problemas): o locatário, os próprios contratos, inclusive os encerrados; o vistoriador, os contratos em
    que tem vistoria e só as vistorias dele; problemas, pela regra de assert_acesso_problemas.
    Locatário ou vistoriador sem nenhum contrato visível no imóvel recebe 403.
    """
    negar_perfil_desconhecido(user)
    im = db.query(Imovel).filter(Imovel.id == imovel_id, Imovel.ativo == True).first()
    if not im:
        return fail("Imóvel não encontrado", status_code=404)

    q = db.query(Contrato).filter(Contrato.imovel_id == imovel_id)
    if user.role == "locatario":
        q = q.filter(Contrato.locatario_id == user.id)
    elif user.role == "vistoriador":
        q = q.filter(Contrato.id.in_(db.query(Checklist.contrato_id).filter(Checklist.vistoriador_id == user.id)))
    contratos = q.all()
    if not contratos and user.role in ("locatario", "vistoriador"):
        raise HTTPException(status_code=403, detail="Você não tem acesso a este imóvel")

    vistorias, problemas = [], []
    if contratos:
        qv = (
            db.query(Checklist)
            .options(selectinload(Checklist.aceite))
            .filter(Checklist.contrato_id.in_([c.id for c in contratos]))
        )
        if user.role == "vistoriador":
            qv = qv.filter(Checklist.vistoriador_id == user.id)
        vistorias = qv.all()

        com_acesso_aos_problemas = []
        for c in contratos:
            try:
                assert_acesso_problemas(c, user)
                com_acesso_aos_problemas.append(c.id)
            except HTTPException:
                pass
        if com_acesso_aos_problemas:
            problemas = (
                db.query(Problema)
                .options(selectinload(Problema.atualizacoes))
                .filter(Problema.contrato_id.in_(com_acesso_aos_problemas))
                .all()
            )

    ordem = {"contrato": 0, "vistoria": 1, "problema": 2}
    eventos = (
        [("contrato", c.created_at, c.id, serialize_contrato(c)) for c in contratos]
        + [("vistoria", v.created_at, v.id, serialize_checklist(v)) for v in vistorias]
        + [("problema", p.created_at, p.id, serialize_problema(p)) for p in problemas]
    )
    eventos.sort(key=lambda e: (e[1] is None, e[1] or datetime.min, ordem[e[0]], e[2]))
    return ok({
        "imovel_id": imovel_id,
        "eventos": [
            {"tipo": tipo, "data": data.isoformat() if data else None, "dados": dados}
            for tipo, data, _, dados in eventos
        ],
    })


@router.put("/{imovel_id}")
def update_imovel(
    imovel_id: str,
    body: ImovelUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_roles("admin", "gestor")),
):
    im = db.query(Imovel).filter(Imovel.id == imovel_id, Imovel.ativo == True).first()
    if not im:
        return fail("Imóvel não encontrado", status_code=404)

    data = body.model_dump(exclude_unset=True)
    endereco_data = data.pop("endereco", None)

    for field, value in data.items():
        setattr(im, field, value)
    # Antes da consulta do endereço, cujo autoflush zeraria o histórico do imóvel
    alterados = campos_alterados(im)

    if body.endereco:
        end = db.query(Endereco).filter(Endereco.imovel_id == imovel_id).first()
        if end:
            _apply_endereco(end, body.endereco, is_new=False)
        else:
            end = Endereco(imovel_id=imovel_id, ativo=True)
            _apply_endereco(end, body.endereco, is_new=True)
            db.add(end)
        alterados += [f"endereco.{c}" for c in campos_alterados(end)]

    db.commit()
    db.refresh(im)
    log_operacao(db, user.id, "update", "imovel", im.id, payload={"campos": alterados})
    return ok(serialize_imovel(im, include_endereco=True))


@router.delete("/{imovel_id}")
def delete_imovel(
    imovel_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_roles("admin", "gestor")),
):
    im = db.query(Imovel).filter(Imovel.id == imovel_id, Imovel.ativo == True).first()
    if not im:
        return fail("Imóvel não encontrado", status_code=404)

    if im.status == "locado":
        return fail("Não é possível excluir um imóvel com contrato ativo (status: locado)", status_code=409)

    im.ativo = False
    if im.endereco:
        im.endereco.ativo = False

    db.commit()
    log_operacao(db, user.id, "delete", "imovel", im.id)
    return ok(None)


@router.get("/{imovel_id}/endereco")
def get_endereco(
    imovel_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    im = db.query(Imovel).filter(Imovel.id == imovel_id, Imovel.ativo == True).first()
    if not im:
        return fail("Imóvel não encontrado", status_code=404)
    assert_acesso_imovel(db, imovel_id, user)

    end = db.query(Endereco).filter(Endereco.imovel_id == imovel_id, Endereco.ativo == True).first()
    if not end:
        return fail("Endereço não encontrado", status_code=404)
    return ok(serialize_endereco(end))


@router.post("/{imovel_id}/endereco")
@router.put("/{imovel_id}/endereco")
@router.patch("/{imovel_id}/endereco")
def upsert_endereco(
    imovel_id: str,
    body: EnderecoCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_roles("admin", "gestor")),
):
    im = db.query(Imovel).filter(Imovel.id == imovel_id, Imovel.ativo == True).first()
    if not im:
        return fail("Imóvel não encontrado", status_code=404)

    end = db.query(Endereco).filter(Endereco.imovel_id == imovel_id).first()
    if end:
        end.ativo = True
        _apply_endereco(end, body, is_new=False)
    else:
        end = Endereco(imovel_id=imovel_id, ativo=True)
        _apply_endereco(end, body, is_new=True)
        db.add(end)
    alterados = campos_alterados(end)
    db.commit()
    db.refresh(end)
    log_operacao(db, user.id, "upsert", "endereco", imovel_id, payload={"campos": alterados})
    return ok(serialize_endereco(end))


# ── Cômodos ───────────────────────────────────────────────────────────────────────

@router.get("/{imovel_id}/comodos")
def list_comodos(
    imovel_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    im = db.query(Imovel).filter(Imovel.id == imovel_id, Imovel.ativo == True).first()
    if not im:
        return fail("Imóvel não encontrado", status_code=404)
    assert_acesso_imovel(db, imovel_id, user)

    ensure_default_comodos(db, imovel_id)
    comodos = (
        db.query(ImovelComodo)
        .filter(ImovelComodo.imovel_id == imovel_id)
        .order_by(ImovelComodo.tipo)
        .all()
    )
    return ok([serialize_comodo(c) for c in comodos])


@router.post("/{imovel_id}/comodos")
def create_comodo(
    imovel_id: str,
    body: ComodoCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_roles("admin", "gestor")),
):
    im = db.query(Imovel).filter(Imovel.id == imovel_id, Imovel.ativo == True).first()
    if not im:
        return fail("Imóvel não encontrado", status_code=404)

    comodo = ImovelComodo(
        imovel_id=imovel_id,
        tipo=body.tipo,
        descricao=body.descricao,
    )
    db.add(comodo)
    db.commit()
    db.refresh(comodo)
    log_operacao(db, user.id, "create", "comodo", comodo.id)
    return ok(serialize_comodo(comodo))


@router.put("/{imovel_id}/comodos/{comodo_id}")
def update_comodo(
    imovel_id: str,
    comodo_id: str,
    body: ComodoUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_roles("admin", "gestor")),
):
    im = db.query(Imovel).filter(Imovel.id == imovel_id, Imovel.ativo == True).first()
    if not im:
        return fail("Imóvel não encontrado", status_code=404)

    comodo = db.query(ImovelComodo).filter(
        ImovelComodo.id == comodo_id,
        ImovelComodo.imovel_id == imovel_id,
    ).first()
    if not comodo:
        return fail("Cômodo não encontrado", status_code=404)

    if body.tipo is not None:
        comodo.tipo = body.tipo
    if body.descricao is not None:
        comodo.descricao = body.descricao
    alterados = campos_alterados(comodo)

    db.commit()
    db.refresh(comodo)
    log_operacao(db, user.id, "update", "comodo", comodo.id, payload={"campos": alterados})
    return ok(serialize_comodo(comodo))


@router.delete("/{imovel_id}/comodos/{comodo_id}")
def delete_comodo(
    imovel_id: str,
    comodo_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_roles("admin", "gestor")),
):
    im = db.query(Imovel).filter(Imovel.id == imovel_id, Imovel.ativo == True).first()
    if not im:
        return fail("Imóvel não encontrado", status_code=404)

    comodo = db.query(ImovelComodo).filter(
        ImovelComodo.id == comodo_id,
        ImovelComodo.imovel_id == imovel_id,
    ).first()
    if not comodo:
        return fail("Cômodo não encontrado", status_code=404)

    if _comodo_em_uso(db, comodo.id):
        return fail(_COMODO_EM_USO, status_code=409)

    db.delete(comodo)
    try:
        db.commit()
    except IntegrityError:
        # Rede de segurança: referência criada entre a checagem e o commit, ou tabela nova com FK para o cômodo
        db.rollback()
        return fail(_COMODO_EM_USO, status_code=409)
    log_operacao(db, user.id, "delete", "comodo", comodo_id)
    return ok(None)

