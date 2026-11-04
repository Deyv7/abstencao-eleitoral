"""Testes do I de Moran em dados sintéticos, com resposta conhecida."""
import numpy as np

from src.espacial import moran, moran_com_teste, vizinhos


def grade(lado: int = 20):
    lat, lon = np.meshgrid(np.linspace(-20, -10, lado), np.linspace(-50, -40, lado))
    return lat.ravel(), lon.ravel()


def test_vizinhos_nao_incluem_o_proprio_ponto():
    lat, lon = grade(5)
    idx, dist = vizinhos(lat, lon, k=4)
    assert idx.shape == (25, 4)
    assert not (idx == np.arange(25)[:, None]).any()
    assert (dist > 0).all()


def test_gradiente_suave_da_moran_alto():
    lat, lon = grade()
    idx, _ = vizinhos(lat, lon, k=4)
    assert moran(lat.copy(), idx) > 0.8


def test_tabuleiro_da_moran_negativo():
    lado = 20
    lat, lon = grade(lado)
    i, j = np.meshgrid(np.arange(lado), np.arange(lado))
    tabuleiro = ((i + j) % 2).ravel().astype(float)
    idx, _ = vizinhos(lat, lon, k=4)
    assert moran(tabuleiro, idx) < -0.8


def test_valores_sorteados_ficam_perto_do_esperado():
    lat, lon = grade()
    idx, _ = vizinhos(lat, lon, k=8)
    x = np.random.default_rng(1).normal(size=len(lat))
    r = moran_com_teste(x, idx, n_perm=199)
    assert abs(r["i"] - r["esperado_sem_dependencia"]) < 0.1
    assert r["p_permutacao"] > 0.01
