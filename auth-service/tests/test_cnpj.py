import pytest

from app.cnpj import format_cnpj, is_valid_cnpj, normalize_cnpj


@pytest.mark.parametrize("cnpj", [
    "11.222.333/0001-81",   # com máscara
    "11222333000181",       # só números
    "12.ABC.345/01DE-35",   # CNPJ alfanumérico
    "12abc34501de35",       # minúsculas também são aceitas
])
def test_valid_cnpjs(cnpj):
    assert is_valid_cnpj(cnpj)


@pytest.mark.parametrize("cnpj", [
    "11.222.333/0001-82",   # dígito verificador errado
    "11222333000180",
    "00000000000000",       # todos iguais
    "11111111111111",
    "1122233300018",        # curto demais
    "112223330001811",      # longo demais
    "AB.CDE.FGH/IJKL-MN",   # dígitos finais precisam ser números
    "",
])
def test_invalid_cnpjs(cnpj):
    assert not is_valid_cnpj(cnpj)


def test_normalize_removes_mask():
    assert normalize_cnpj("11.222.333/0001-81") == "11222333000181"


def test_format_adds_mask():
    assert format_cnpj("11222333000181") == "11.222.333/0001-81"
