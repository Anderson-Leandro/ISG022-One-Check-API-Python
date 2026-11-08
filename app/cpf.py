"""CPF: validação no cadastro e máscara nas respostas (LGPD, minimização)."""

import re


def _digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor)


def _formatar(d: str) -> str:
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"


def validar_cpf(valor: str | None) -> str | None:
    """Aceita com ou sem pontuação e devolve no formato 000.000.000-00. Vazio vira None."""
    if valor is None or not valor.strip():
        return None
    if re.search(r"[^\d.\-\s]", valor):
        raise ValueError("CPF inválido")
    d = _digitos(valor)
    if len(d) != 11 or len(set(d)) == 1:
        raise ValueError("CPF inválido")
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (soma * 10 % 11) % 10 != int(d[n]):
            raise ValueError("CPF inválido")
    return _formatar(d)


def mascarar_cpf(valor: str | None) -> str | None:
    """Mostra só os seis dígitos do meio: ***.982.247-**. Valores antigos fora do formato ficam todo mascarados."""
    if not valor:
        return None
    d = _digitos(valor)
    if len(d) != 11:
        return "***.***.***-**"
    return f"***.{d[3:6]}.{d[6:9]}-**"
