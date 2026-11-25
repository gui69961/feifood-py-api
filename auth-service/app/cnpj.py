"""Validação de CNPJ (numérico e alfanumérico).

Atenção: isto confere o FORMATO e os dígitos verificadores. Não consulta a Receita
Federal, então não garante que a empresa exista de fato.
"""
import re

_PATTERN = re.compile(r"^[0-9A-Z]{12}[0-9]{2}$")
_WEIGHTS_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_WEIGHTS_2 = [6] + _WEIGHTS_1


def normalize_cnpj(value: str) -> str:
    """Remove pontos, barra e traço e deixa em maiúsculas."""
    return re.sub(r"[.\-/\s]", "", value).upper()


def _check_digit(chars: str, weights: list[int]) -> int:
    # Cada caractere vale (código ASCII - 48): '0'..'9' valem 0..9 e 'A'..'Z' valem 17..42.
    total = sum((ord(c) - 48) * w for c, w in zip(chars, weights))
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


def is_valid_cnpj(value: str) -> bool:
    cnpj = normalize_cnpj(value)
    if not _PATTERN.match(cnpj):
        return False
    if len(set(cnpj)) == 1:  # 00000000000000, 11111111111111...
        return False
    first = _check_digit(cnpj[:12], _WEIGHTS_1)
    second = _check_digit(cnpj[:12] + str(first), _WEIGHTS_2)
    return cnpj[12:] == f"{first}{second}"


def format_cnpj(value: str) -> str:
    c = normalize_cnpj(value)
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else value
