from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import assert_acesso_imovel, get_current_user, require_roles
from app.geocoding import buscar_coordenadas
from app.models import Checklist, Contrato, Endereco, Imovel, ImovelComodo, Usuario
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
    serialize_comodo,
    serialize_endereco,
    serialize_imovel,
)

router = APIRouter(prefix="/imoveis", tags=["imoveis"])


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
    im = (
        db.query(Imovel)
        .options(joinedload(Imovel.endereco))
        .filter(Imovel.id == imovel_id, Imovel.ativo == True)
        .first()
    )
    if not im:
        return fail("Imóvel não encontrado")
    assert_acesso_imovel(db, imovel_id, user)
    return ok(serialize_imovel(im, include_endereco=True))


@router.put("/{imovel_id}")
def update_imovel(
    imovel_id: str,
    body: ImovelUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_roles("admin", "gestor")),
):
    im = db.query(Imovel).filter(Imovel.id == imovel_id, Imovel.ativo == True).first()
    if not im:
        return fail("Imóvel não encontrado")

    data = body.model_dump(exclude_unset=True)
    endereco_data = data.pop("endereco", None)

    for field, value in data.items():
        setattr(im, field, value)

    if body.endereco:
        end = db.query(Endereco).filter(Endereco.imovel_id == imovel_id).first()
        if end:
            _apply_endereco(end, body.endereco, is_new=False)
        else:
            end = Endereco(imovel_id=imovel_id, ativo=True)
            _apply_endereco(end, body.endereco, is_new=True)
            db.add(end)

    db.commit()
    db.refresh(im)
    log_operacao(db, user.id, "update", "imovel", im.id)
    return ok(serialize_imovel(im, include_endereco=True))


@router.delete("/{imovel_id}")
def delete_imovel(
    imovel_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_roles("admin", "gestor")),
):
    im = db.query(Imovel).filter(Imovel.id == imovel_id, Imovel.ativo == True).first()
    if not im:
        return fail("Imóvel não encontrado")

    if im.status == "locado":
        return fail("Não é possível excluir um imóvel com contrato ativo (status: locado)")

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
        return fail("Imóvel não encontrado")
    assert_acesso_imovel(db, imovel_id, user)

    end = db.query(Endereco).filter(Endereco.imovel_id == imovel_id, Endereco.ativo == True).first()
    if not end:
        return fail("Endereço não encontrado")
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
        return fail("Imóvel não encontrado")

    end = db.query(Endereco).filter(Endereco.imovel_id == imovel_id).first()
    if end:
        end.ativo = True
        _apply_endereco(end, body, is_new=False)
    else:
        end = Endereco(imovel_id=imovel_id, ativo=True)
        _apply_endereco(end, body, is_new=True)
        db.add(end)
    db.commit()
    db.refresh(end)
    log_operacao(db, user.id, "upsert", "endereco", imovel_id)
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
        return fail("Imóvel não encontrado")
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
        return fail("Imóvel não encontrado")

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
        return fail("Imóvel não encontrado")

    comodo = db.query(ImovelComodo).filter(
        ImovelComodo.id == comodo_id,
        ImovelComodo.imovel_id == imovel_id,
    ).first()
    if not comodo:
        return fail("Cômodo não encontrado")

    if body.tipo is not None:
        comodo.tipo = body.tipo
    if body.descricao is not None:
        comodo.descricao = body.descricao

    db.commit()
    db.refresh(comodo)
    log_operacao(db, user.id, "update", "comodo", comodo.id)
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
        return fail("Imóvel não encontrado")

    comodo = db.query(ImovelComodo).filter(
        ImovelComodo.id == comodo_id,
        ImovelComodo.imovel_id == imovel_id,
    ).first()
    if not comodo:
        return fail("Cômodo não encontrado")

    db.delete(comodo)
    db.commit()
    log_operacao(db, user.id, "delete", "comodo", comodo.id)
    return ok(None)

