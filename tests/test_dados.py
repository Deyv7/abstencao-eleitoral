"""Testes de dados sobre os Parquet locais (brutos e processados).

Rodam sem BigQuery: python -m pytest
"""
import numpy as np
import pandas as pd
import pytest

from src.features import ALVO, BRUTOS, PROCESSADOS, VARIAVEIS

ANOS = [2022, 2018]

# Municípios que existem no diretório da Base dos Dados mas não tiveram
# votação nas eleições analisadas. Boa Esperança do Norte (MT) foi instalado
# depois de 2022 e não aparece na votação de 2018 nem na de 2022.
FALTANTES_ESPERADOS = {"5101837"}

# Única divergência entre aptos e comparecimento + abstenções encontrada na
# fonte para presidente, 1º turno, fora do exterior: Manaus (AM), zona 68, em
# 2022, com 84 eleitores a mais em aptos. A mesma diferença está na tabela
# municipal da Base dos Dados. O teste aceita só esta exceção, com este valor.
EXCECOES_CONCILIACAO = {2022: {"1302603": 84}, 2018: {}}


@pytest.fixture(scope="module", params=ANOS)
def ano(request):
    return request.param


@pytest.fixture(scope="module")
def municipios(ano):
    return pd.read_parquet(PROCESSADOS / f"municipios_{ano}.parquet")


@pytest.fixture(scope="module")
def zonas(ano):
    return pd.read_parquet(BRUTOS / f"votacao_zona_{ano}.parquet")


def test_extracao_fixou_cargo_turno_e_tipo(zonas):
    assert set(zonas["cargo"]) == {"presidente"}
    assert set(zonas["turno"]) == {1}
    assert set(zonas["tipo_eleicao"]) == {"eleicao ordinaria"}
    assert "ZZ" not in set(zonas["sigla_uf"])


def test_zona_aparece_uma_vez_por_municipio(zonas):
    assert not zonas.duplicated(["id_municipio", "zona"]).any()


def test_municipio_unico(municipios):
    assert municipios["id_municipio"].is_unique
    assert municipios["id_municipio"].str.fullmatch(r"\d{7}").all()


def test_cobertura_de_municipios(municipios):
    diretorio = pd.read_parquet(BRUTOS / "diretorio_municipios.parquet")
    faltantes = set(diretorio["id_municipio"]) - set(municipios["id_municipio"])
    assert faltantes == FALTANTES_ESPERADOS
    assert len(municipios) == 5570
    assert municipios["sigla_uf"].nunique() == 27


def test_taxas_entre_0_e_1(municipios):
    assert municipios["taxa_abstencao"].between(0, 1).all()
    for c in ["pct_16_17", "pct_70_mais", "pct_feminino", "pct_baixa_escolaridade",
              "pct_superior"]:
        assert municipios[c].between(0, 100).all(), c


def test_conciliacao_aptos(municipios, ano):
    diferenca = municipios["aptos"] - municipios["comparecimento"] - municipios["abstencoes"]
    divergentes = dict(zip(municipios.loc[diferenca != 0, "id_municipio"],
                           diferenca[diferenca != 0].astype(int)))
    assert divergentes == EXCECOES_CONCILIACAO[ano]


def test_soma_das_zonas_bate_com_tabela_municipal(municipios, ano):
    ref = pd.read_parquet(BRUTOS / f"votacao_municipio_{ano}.parquet")
    juntos = municipios.merge(ref, on="id_municipio", suffixes=("", "_ref"),
                              how="outer", validate="1:1")
    assert len(juntos) == len(municipios) == len(ref)
    for c in ["aptos", "comparecimento", "abstencoes"]:
        assert (juntos[c] == juntos[f"{c}_ref"]).all(), c


def test_sem_nulos_nas_variaveis_usadas(municipios):
    usadas = VARIAVEIS + [ALVO, "regiao", "sigla_uf"]
    assert municipios[usadas].notna().all().all()
    assert np.isfinite(municipios[VARIAVEIS + [ALVO]].astype(float)).all().all()


def test_perfil_cobre_todas_as_categorias(ano):
    perfil = pd.read_parquet(BRUTOS / f"perfil_eleitorado_{ano}.parquet")
    instrucao = perfil[[f"instrucao_{c}" for c in range(9)]].sum(axis=1)
    genero = perfil[["genero_feminino", "genero_masculino", "genero_nao_informado"]].sum(axis=1)
    assert (instrucao == perfil["eleitores_perfil"]).all()
    assert (genero == perfil["eleitores_perfil"]).all()


def test_perfil_e_votacao_falam_do_mesmo_eleitorado(municipios):
    # O perfil é uma fotografia do cadastro e não precisa bater exatamente com
    # os aptos da votação, mas não pode estar longe.
    razao = municipios["eleitores_perfil"] / municipios["aptos"]
    assert razao.between(0.9, 1.1).all()


def test_agregacao_recusa_zona_repetida():
    # Simula a armadilha da fonte: a mesma zona repetida (por exemplo, uma vez
    # por cargo). A agregação tem que parar em vez de somar em dobro.
    from src.features import agregar_votacao

    base = {"ano": 2022, "turno": 1, "cargo": "presidente",
            "tipo_eleicao": "eleicao ordinaria", "sigla_uf": "DF",
            "id_municipio": "5300108", "zona": "1", "aptos": 100,
            "comparecimento": 80, "abstencoes": 20}
    repetida = pd.DataFrame([base, base])
    with pytest.raises(ValueError):
        agregar_votacao(repetida)


# Fernando de Noronha (PE) fica a ~370 km da costa e não está na malha de UFs em
# qualidade mínima, que só tem o continente e as ilhas próximas.
FORA_DA_MALHA_ESPERADOS = {"2605459"}


def test_ponto_de_cada_municipio_cai_no_proprio_estado(municipios):
    # O ponto de cada município tem que estar dentro do contorno do seu estado, ou a
    # menos de 10 km dele (a malha simplificada corta pontas de costa e de divisa).
    # Pegou o centroide de Vitória (ES) 100 km no mar, puxado pela ilha de Trindade.
    import json

    from src.exportar_web import CODIGOS_UF

    malha = json.loads((BRUTOS / "malha_uf_ibge.geojson").read_text(encoding="utf-8"))
    aneis = {}
    for f in malha["features"]:
        geo = f["geometry"]
        poligonos = [geo["coordinates"]] if geo["type"] == "Polygon" else geo["coordinates"]
        aneis[CODIGOS_UF[f["properties"]["codarea"]]] = [np.array(p[0]) for p in poligonos]

    def dentro(x, y, r):
        xs, ys = r[:, 0], r[:, 1]
        xj, yj = np.roll(xs, 1), np.roll(ys, 1)
        cruza = ((ys > y) != (yj > y)) & (x < (xj - xs) * (y - ys) / (yj - ys + 1e-15) + xs)
        return cruza.sum() % 2 == 1

    def km_ate_contorno(x, y, rs):
        return min(np.hypot((r[:, 0] - x) * np.cos(np.radians(y)), r[:, 1] - y).min() for r in rs) * 111

    longe = {}
    for m in municipios.itertuples():
        rs = aneis[m.sigla_uf]
        if any(dentro(m.longitude, m.latitude, r) for r in rs):
            continue
        d = km_ate_contorno(m.longitude, m.latitude, rs)
        if d > 10:
            longe[m.id_municipio] = (m.nome, round(d))
    assert set(longe) == FORA_DA_MALHA_ESPERADOS, longe
