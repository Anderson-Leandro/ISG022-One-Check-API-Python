import json
from unittest.mock import MagicMock, patch

from app.geocoding import buscar_coordenadas, buscar_endereco_por_cep


def test_buscar_endereco_por_cep_invalido():
    assert buscar_endereco_por_cep("123") == {}
    assert buscar_endereco_por_cep("") == {}


def test_buscar_endereco_por_cep_sucesso():
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(
        {
            "logradouro": "Praça da Sé",
            "bairro": "Sé",
            "localidade": "São Paulo",
            "uf": "SP",
        }
    ).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = buscar_endereco_por_cep("01001-000")
        assert res["logradouro"] == "Praça da Sé"
        assert res["cidade"] == "São Paulo"
        assert res["estado"] == "SP"


def test_buscar_endereco_por_cep_erro_api():
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"erro": True}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = buscar_endereco_por_cep("99999-999")
        assert res == {}


def test_buscar_coordenadas_vazio():
    assert buscar_coordenadas("") is None
    assert buscar_coordenadas("   ") is None


def test_buscar_coordenadas_sucesso():
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps([{"lat": "-23.5505", "lon": "-46.6333"}]).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = buscar_coordenadas("Praça da Sé, São Paulo, SP, Brasil")
        assert res is not None
        assert res["latitude"] == -23.5505
        assert res["longitude"] == -46.6333


def test_buscar_coordenadas_nao_encontrado():
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps([]).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = buscar_coordenadas("Endereco Que Nao Existe 99999")
        assert res is None
