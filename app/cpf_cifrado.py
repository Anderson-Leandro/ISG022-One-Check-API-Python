"""CPF cifrado em repouso (SEC-031, ADR-0014).

A coluna usuarios.cpf guarda um token Fernet (AES-128-CBC com HMAC-SHA256): quem lê o banco ou um backup
não vê o CPF. A ORM cifra ao gravar e decifra ao ler, então as rotas e as respostas não mudam.

As chaves vêm de CPF_CHAVES (app/config.py). Cada uma é derivada com SHA-256 para os 32 bytes do Fernet,
então serve qualquer segredo longo (inclusive o generateValue do Render). A primeira cifra, todas decifram.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlalchemy import String, column, select, table, update
from sqlalchemy.types import TypeDecorator

from app.config import CPF_CHAVES

# Todo token Fernet começa pela versão 0x80, que em base64 vira "gAAAAA"; um CPF em texto começa por dígito
_PREFIXO_TOKEN = "gAAAAA"
TAMANHO_COLUNA = 255


def _fernet(segredo: str) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(segredo.encode()).digest()))


class Cifra:
    def __init__(self, chaves: list[str]):
        self.atual = _fernet(chaves[0])
        self.todas = MultiFernet([_fernet(c) for c in chaves])

    def cifrar(self, texto: str) -> str:
        return self.atual.encrypt(texto.encode()).decode()

    def decifrar(self, valor: str) -> str:
        """Decifra com qualquer chave conhecida. Um valor em texto (de antes da migração) volta como está."""
        if not valor.startswith(_PREFIXO_TOKEN):
            return valor
        try:
            return self.todas.decrypt(valor.encode()).decode()
        except InvalidToken:
            # Fail secure: sem a chave, a API não inventa um CPF nem devolve o token
            raise RuntimeError("CPF cifrado com uma chave que não está em CPF_CHAVES") from None

    def rotacionar(self, valor: str) -> str:
        """Token recifrado com a chave atual (texto puro é só cifrado). InvalidToken se nenhuma chave serve."""
        if not valor.startswith(_PREFIXO_TOKEN):
            return self.cifrar(valor)
        return self.todas.rotate(valor.encode()).decode()

    def usa_chave_atual(self, valor: str) -> bool:
        try:
            self.atual.decrypt(valor.encode())
            return True
        except InvalidToken:
            return False


cifra = Cifra(CPF_CHAVES)


class CpfCifrado(TypeDecorator):
    """Tipo da coluna: cifra ao gravar e decifra ao ler."""

    impl = String(TAMANHO_COLUNA)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else cifra.cifrar(value)

    def process_result_value(self, value, dialect):
        return None if value is None else cifra.decifrar(value)


# A coluna sem o TypeDecorator: para ler e gravar o valor bruto
_USUARIOS_BRUTO = table("usuarios", column("id", String), column("cpf", String))


def cifrar_cpfs_em_texto(conn, c: Cifra | None = None) -> int:
    """Cifra os CPFs ainda em texto (banco de antes do SEC-031). Roda na inicialização.

    Só olha as linhas sem o prefixo de token, então não decifra nada e custa uma consulta quando não há
    o que fazer. A troca de chave não é feita aqui: ver `rotacionar`."""
    c = c or cifra
    t = _USUARIOS_BRUTO
    linhas = conn.execute(
        select(t.c.id, t.c.cpf).where(t.c.cpf.is_not(None), t.c.cpf.not_like(f"{_PREFIXO_TOKEN}%"))
    ).all()
    for id_, bruto in linhas:
        conn.execute(update(t).where(t.c.id == id_).values(cpf=c.cifrar(bruto)))
    return len(linhas)


def rotacionar(conn, c: Cifra | None = None, aplicar: bool = True) -> dict:
    """Recifra com a chave atual os CPFs de chaves antigas (scripts/rotacionar_chave_cpf.py).

    Devolve {"atual": n, "recifrados": n, "ilegiveis": [ids]}. Com aplicar=False, só conta. Um CPF que
    nenhuma chave decifra fica como está e aparece em "ilegiveis": a chave antiga não deve sair ainda."""
    c = c or cifra
    t = _USUARIOS_BRUTO
    resultado = {"atual": 0, "recifrados": 0, "ilegiveis": []}
    for id_, bruto in conn.execute(select(t.c.id, t.c.cpf).where(t.c.cpf.is_not(None))):
        if bruto.startswith(_PREFIXO_TOKEN) and c.usa_chave_atual(bruto):
            resultado["atual"] += 1
            continue
        try:
            novo = c.rotacionar(bruto)
        except InvalidToken:
            resultado["ilegiveis"].append(id_)
            continue
        if aplicar:
            conn.execute(update(t).where(t.c.id == id_).values(cpf=novo))
        resultado["recifrados"] += 1
    return resultado
