"""Política de senha, aplicada ao criar usuário e ao trocar senha.

Vale para senhas novas. A senha já cadastrada fora da política continua entrando, mas o login
marca a conta com senha_expirada (SEC-029), e até a troca o token só serve para trocar a senha. A lista não substitui uma base de senhas vazadas, mas
recusa os padrões mais usados em credential stuffing.
"""

import re

SENHA_MIN = 10
# O bcrypt ignora o que passa de 72 bytes: duas senhas com o mesmo começo seriam iguais
SENHA_MAX_BYTES = 72

# Comparadas depois de tirar números e símbolos: "Senha@2024" vira "senha"
_PALAVRAS_COMUNS = frozenset(
    {
        "senha",
        "password",
        "passw",
        "pass",
        "qwerty",
        "qwertyuiop",
        "asdfgh",
        "asdfghjkl",
        "zxcvbnm",
        "admin",
        "administrador",
        "root",
        "user",
        "usuario",
        "teste",
        "test",
        "abc",
        "abcdef",
        "abcdefghij",
        "mudar",
        "mudarsenha",
        "trocar",
        "acesso",
        "login",
        "welcome",
        "bemvindo",
        "iloveyou",
        "teamo",
        "brasil",
        "onecheck",
        "vistoria",
        "imobiliaria",
        "aluguel",
        "contrato",
        "locatario",
        "vistoriador",
        "gestor",
        "segredo",
        "secret",
        "default",
        "master",
        "dragon",
        "monkey",
        "football",
        "futebol",
        "flamengo",
        "corinthians",
        "palmeiras",
        "saopaulo",
        "gremio",
        "cruzeiro",
        "vasco",
        "qazwsx",
        "qweasd",
        "qwe",
        "qwer",
        "asd",
        "asdf",
        "zxc",
        "zxcv",
    }
)


def validar_senha(senha: str) -> str:
    if len(senha) < SENHA_MIN:
        raise ValueError(f"A senha deve ter pelo menos {SENHA_MIN} caracteres")
    if len(senha.encode()) > SENHA_MAX_BYTES:
        raise ValueError(f"A senha deve ter no máximo {SENHA_MAX_BYTES} bytes")
    letras = re.sub(r"[\d\W_]+", "", senha.lower())
    if not letras:
        raise ValueError("A senha não pode ter só números e símbolos")
    if letras in _PALAVRAS_COMUNS or len(set(senha.lower())) < 5:
        raise ValueError("Senha muito comum ou previsível; escolha outra")
    return senha
