from datetime import date
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from app.config import MAX_UPLOAD_MB, UPLOAD_DIR
from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import (
    Checklist,
    ChecklistItem,
    ChecklistItemFoto,
    Contrato,
    ImovelComodo,
    ItemVistoria,
    Usuario,
)
from app.schemas import AddChecklistItemRequest, ItemUpdateRequest, fail, ok
from app.serializers import (
    foto_url,
    get_comodos_for_checklist,
    log_operacao,
    serialize_checklist,
    serialize_foto,
    serialize_item,
)

router = APIRouter(tags=["checklists"])


def _get_checklist(db: Session, checklist_id: str) -> Checklist | None:
    return (
        db.query(Checklist)
        .options(joinedload(Checklist.itens).joinedload(ChecklistItem.fotos))
        .filter(Checklist.id == checklist_id)
        .first()
    )


def _assert_vistoriador(checklist: Checklist, user: Usuario) -> None:
    if user.role == "admin":
        return
    if checklist.vistoriador_id != user.id:
        raise HTTPException(status_code=403, detail="Vistoriador não autorizado neste checklist")


def _assert_pode_aceitar(checklist: Checklist, user: Usuario, db: Session) -> None:
    if user.role in ("admin", "gestor"):
        return
    raise HTTPException(status_code=403, detail="Sem permissão para aceitar ou rejeitar esta vistoria")


@router.get("/itens-vistoria")
def list_itens_vistoria(db: Session = Depends(get_db), _: Usuario = Depends(get_current_user)):
    rows = db.query(ItemVistoria).order_by(ItemVistoria.nome).all()
    return ok([{"id": r.id, "nome": r.nome, "categoria": r.categoria} for r in rows])


def _assert_pode_ver_checklist(checklist: Checklist, user: Usuario, db: Session) -> None:
    if user.role in ("admin", "gestor", "visualizador"):
        return
    if user.role == "vistoriador" and checklist.vistoriador_id == user.id:
        return
    if user.role == "locatario":
        contrato = db.query(Contrato).filter(Contrato.id == checklist.contrato_id).first()
        if contrato and contrato.locatario_id == user.id:
            return
    raise HTTPException(status_code=403, detail="Sem permissão para ver esta vistoria")


@router.get("/checklists/{checklist_id}")
def get_checklist(
    checklist_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ck = _get_checklist(db, checklist_id)
    if not ck:
        return fail("Checklist não encontrado")
    _assert_pode_ver_checklist(ck, user, db)
    comodos = get_comodos_for_checklist(db, ck)
    return ok(serialize_checklist(ck, include_itens=True, comodos=comodos))


@router.post("/checklists/{checklist_id}/itens")
def add_item(
    checklist_id: str,
    body: AddChecklistItemRequest,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ck = _get_checklist(db, checklist_id)
    if not ck:
        return fail("Checklist não encontrado")
    _assert_vistoriador(ck, user)

    if ck.status != "em_preenchimento":
        return fail(f"Não é possível adicionar itens a um checklist com status '{ck.status}'")

    if body.estado not in ("otimo", "bom", "regular", "ruim"):
        return fail("Estado inválido")

    # Validar que comodo existe
    contrato = db.query(Contrato).filter(Contrato.id == ck.contrato_id).first()
    if contrato:
        comodo = db.query(ImovelComodo).filter(
            ImovelComodo.id == body.comodo_id,
            ImovelComodo.imovel_id == contrato.imovel_id,
        ).first()
        if not comodo:
            return fail("Cômodo não encontrado")

    # Validar que item_vistoria existe
    it_vist = db.query(ItemVistoria).filter(ItemVistoria.id == body.item_vistoria_id).first()
    if not it_vist:
        return fail("Item de vistoria não encontrado")

    existing = (
        db.query(ChecklistItem)
        .filter(
            ChecklistItem.checklist_id == checklist_id,
            ChecklistItem.comodo_id == body.comodo_id,
            ChecklistItem.item_vistoria_id == body.item_vistoria_id,
        )
        .first()
    )
    if existing:
        existing.estado = body.estado
        existing.observacao = body.observacao
        db.commit()
        db.refresh(existing)
        return ok(serialize_item(existing))

    item = ChecklistItem(
        checklist_id=checklist_id,
        comodo_id=body.comodo_id,
        item_vistoria_id=body.item_vistoria_id,
        estado=body.estado,
        observacao=body.observacao,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    log_operacao(db, user.id, "create", "checklist_item", item.id)
    return ok(serialize_item(item))


@router.put("/checklists/{checklist_id}/itens/{item_id}")
def update_item(
    checklist_id: str,
    item_id: str,
    body: ItemUpdateRequest,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ck = _get_checklist(db, checklist_id)
    if not ck:
        return fail("Checklist não encontrado")
    _assert_vistoriador(ck, user)

    if ck.status != "em_preenchimento":
        return fail(f"Não é possível editar itens de um checklist com status '{ck.status}'")

    item = (
        db.query(ChecklistItem)
        .options(joinedload(ChecklistItem.fotos))
        .filter(ChecklistItem.id == item_id)
        .first()
    )
    if not item:
        return fail("Item não encontrado")

    if item.checklist_id != checklist_id:
        return fail("Este item não pertence ao checklist informado")

    if body.estado is not None:
        if body.estado not in ("otimo", "bom", "regular", "ruim"):
            return fail("Estado inválido")
        item.estado = body.estado
    if body.observacao is not None:
        item.observacao = body.observacao

    db.commit()
    db.refresh(item)
    log_operacao(db, user.id, "update", "checklist_item", item.id)
    return ok(serialize_item(item))


@router.post("/checklists/{checklist_id}/itens/{item_id}/fotos")
async def upload_foto(
    checklist_id: str,
    item_id: str,
    foto: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ck = _get_checklist(db, checklist_id)
    if not ck:
        return fail("Checklist não encontrado")
    _assert_vistoriador(ck, user)

    if ck.status != "em_preenchimento":
        return fail(f"Não é possível adicionar fotos a um checklist com status '{ck.status}'")

    item = (
        db.query(ChecklistItem)
        .options(joinedload(ChecklistItem.fotos))
        .filter(ChecklistItem.id == item_id)
        .first()
    )
    if not item:
        return fail("Item não encontrado")

    if item.checklist_id != checklist_id:
        return fail("Este item não pertence ao checklist informado")

    if not item.estado:
        return fail("Selecione o estado do item antes de enviar a foto")

    content = await foto.read()
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        return fail(f"Arquivo excede {MAX_UPLOAD_MB}MB")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(foto.filename or "foto.jpg").suffix or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = UPLOAD_DIR / filename
    filepath.write_bytes(content)

    for old in list(item.fotos):
        old_path = UPLOAD_DIR / old.arquivo
        if old_path.exists():
            old_path.unlink(missing_ok=True)
        db.delete(old)

    foto_row = ChecklistItemFoto(item_id=item.id, arquivo=filename)
    db.add(foto_row)
    db.commit()
    db.refresh(foto_row)
    log_operacao(db, user.id, "upload", "checklist_foto", foto_row.id)

    return ok({"id": foto_row.id, "checklist_item_id": item.id, "url": foto_url(filename)})


@router.delete("/checklists/{checklist_id}/itens/{item_id}/fotos/{foto_id}")
def delete_foto(
    checklist_id: str,
    item_id: str,
    foto_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ck = _get_checklist(db, checklist_id)
    if not ck:
        return fail("Checklist não encontrado")
    _assert_vistoriador(ck, user)

    if ck.status != "em_preenchimento":
        return fail(f"Não é possível excluir fotos de um checklist com status '{ck.status}'")

    foto_row = (
        db.query(ChecklistItemFoto)
        .join(ChecklistItem)
        .filter(
            ChecklistItemFoto.id == foto_id,
            ChecklistItem.id == item_id,
            ChecklistItem.checklist_id == checklist_id,
        )
        .first()
    )
    if not foto_row:
        return fail("Foto não encontrada")

    old_path = UPLOAD_DIR / foto_row.arquivo
    if old_path.exists():
        old_path.unlink(missing_ok=True)
    db.delete(foto_row)
    db.commit()
    log_operacao(db, user.id, "delete", "checklist_foto", foto_id)
    return ok(None)


@router.patch("/checklists/{checklist_id}/submeter")
def submit_checklist(
    checklist_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ck = _get_checklist(db, checklist_id)
    if not ck:
        return fail("Checklist não encontrado")
    _assert_vistoriador(ck, user)

    if ck.status in ("pendente_aceite", "aceito") or ck.status != "em_preenchimento":
        return fail("Checklist já foi submetido")

    filled = (
        db.query(ChecklistItem)
        .filter(ChecklistItem.checklist_id == checklist_id, ChecklistItem.estado.isnot(None))
        .count()
    )
    if filled == 0:
        return fail("Preencha ao menos um item antes de submeter")

    ck.status = "pendente_aceite"
    ck.data_vistoria = date.today()
    db.commit()
    db.refresh(ck)
    log_operacao(db, user.id, "update", "checklist", checklist_id, "submeter")
    return ok(serialize_checklist(ck, include_itens=True))


@router.patch("/checklists/{checklist_id}/enviar-para-aceite")
def enviar_para_aceite(
    checklist_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_roles("admin", "gestor")),
):
    ck = _get_checklist(db, checklist_id)
    if not ck:
        return fail("Checklist não encontrado")

    if ck.status != "em_preenchimento":
        return fail(f"Não é possível enviar para aceite um checklist com status '{ck.status}'")

    filled = (
        db.query(ChecklistItem)
        .filter(ChecklistItem.checklist_id == checklist_id, ChecklistItem.estado.isnot(None))
        .count()
    )
    if filled == 0:
        return fail("O checklist deve ter ao menos um item preenchido antes de ser enviado para aceite")

    ck.status = "pendente_aceite"
    db.commit()
    db.refresh(ck)
    log_operacao(db, user.id, "update", "checklist", checklist_id, "enviar_para_aceite")
    return ok(serialize_checklist(ck, include_itens=True))


@router.patch("/checklists/{checklist_id}/aceitar")
def aceitar_checklist(
    checklist_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ck = _get_checklist(db, checklist_id)
    if not ck:
        return fail("Checklist não encontrado")
    _assert_pode_aceitar(ck, user, db)
    if ck.status != "pendente_aceite":
        return fail("Checklist não está pendente de aceite")
    ck.status = "aceito"
    db.commit()
    log_operacao(db, user.id, "accept", "checklist", checklist_id)
    return ok({"id": checklist_id, "status": ck.status})


@router.patch("/checklists/{checklist_id}/rejeitar")
def rejeitar_checklist(
    checklist_id: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ck = _get_checklist(db, checklist_id)
    if not ck:
        return fail("Checklist não encontrado")
    _assert_pode_aceitar(ck, user, db)
    if ck.status != "pendente_aceite":
        return fail("Checklist não está pendente de aceite")
    ck.status = "rejeitado"
    db.commit()
    log_operacao(db, user.id, "reject", "checklist", checklist_id)
    return ok({"id": checklist_id, "status": ck.status})
