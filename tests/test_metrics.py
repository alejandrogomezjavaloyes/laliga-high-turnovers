"""Tests de los cálculos sobre robos altos."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from metrics import (  # noqa: E402
    HIGH_TURNOVER_X,
    by_distance,
    lane_of,
    league_totals,
    summarise,
    wilson_interval,
    zone_grid,
)


def make(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["lane"] = frame["start_y"].map(lane_of)
    return frame


def turnover(team="A", x=90.0, y=40.0, shot=False, shots=0, xg=0.0, goal=False, secs=None):
    return {
        "match_id": 1,
        "team": team,
        "start_x": x,
        "start_y": y,
        "start_type": "Ball Recovery",
        "start_player": "jugador",
        "ended_in_shot": shot,
        "shots": shots,
        "shot_xg": xg,
        "is_goal": goal,
        "seconds_to_shot": secs,
    }


class TestUmbral:
    def test_el_umbral_sale_de_los_40_metros(self):
        # 40 m sobre un campo de 105 m, en unidades StatsBomb de 120.
        assert HIGH_TURNOVER_X == pytest.approx(74.2857, abs=1e-3)


class TestCarril:
    def test_el_centro_es_el_tercio_central(self):
        assert lane_of(40.0) == "Centro"
        assert lane_of(26.667) == "Centro"
        assert lane_of(53.332) == "Centro"

    def test_las_bandas_quedan_fuera(self):
        assert lane_of(0.0) == "Bandas"
        assert lane_of(26.666) == "Bandas"
        assert lane_of(53.334) == "Bandas"
        assert lane_of(80.0) == "Bandas"


class TestWilson:
    def test_el_intervalo_contiene_la_proporcion(self):
        low, high = wilson_interval(36, 119)
        assert low < 36 / 119 < high

    def test_con_muestra_pequena_el_intervalo_es_mas_ancho(self):
        ancho_pequeno = wilson_interval(3, 10)
        ancho_grande = wilson_interval(300, 1000)
        assert (ancho_pequeno[1] - ancho_pequeno[0]) > (ancho_grande[1] - ancho_grande[0])

    def test_nunca_se_sale_de_cero_uno(self):
        low, high = wilson_interval(0, 5)
        assert low >= 0.0
        low, high = wilson_interval(5, 5)
        assert high <= 1.0

    def test_sin_datos_no_revienta(self):
        assert wilson_interval(0, 0) == (0.0, 0.0)


class TestSummarise:
    def test_cuenta_y_divide_bien(self):
        data = make([
            turnover("A", shot=True, shots=1, xg=0.2),
            turnover("A", shot=False),
            turnover("B", shot=True, shots=2, xg=0.5, goal=True),
        ])
        out = summarise(data, "team").set_index("team")
        assert out.loc["A", "turnovers"] == 2
        assert out.loc["A", "shot_ending"] == 1
        assert out.loc["A", "shot_rate"] == pytest.approx(0.5)
        assert out.loc["B", "goals"] == 1
        assert out.loc["B", "xg_per_turnover"] == pytest.approx(0.5)

    def test_anade_el_intervalo(self):
        data = make([turnover(shot=True) for _ in range(10)])
        out = summarise(data, "team")
        assert out.loc[0, "ci_low"] <= out.loc[0, "shot_rate"] <= out.loc[0, "ci_high"]


class TestRejilla:
    def test_no_pierde_ningun_robo(self):
        # Incluye los bordes: y = 80.0 y x justo en el umbral.
        data = make([
            turnover(x=HIGH_TURNOVER_X, y=0.0),
            turnover(x=119.9, y=80.0),
            turnover(x=100.0, y=40.0),
        ])
        grid = zone_grid(data, min_count=1)
        assert grid["turnovers"].sum() == len(data)

    def test_las_casillas_flojas_quedan_vacias(self):
        data = make([turnover(x=90.0, y=40.0, shot=True)])
        grid = zone_grid(data, min_count=10)
        assert grid["shot_rate"].isna().all()


class TestDistancia:
    def test_reparte_en_tres_franjas(self):
        data = make([
            turnover(x=80.0),
            turnover(x=90.0),
            turnover(x=110.0),
        ])
        out = by_distance(data)
        assert list(out["turnovers"]) == [1, 1, 1]

    def test_los_120_entran_en_la_ultima_franja(self):
        data = make([turnover(x=120.0)])
        out = by_distance(data).set_index("band")
        assert out.loc["menos de 18 m", "turnovers"] == 1


class TestTotales:
    def test_calcula_las_cifras_de_cabecera(self):
        data = make([
            turnover(y=40.0, shot=True, secs=5.0),
            turnover(y=40.0, shot=False),
            turnover(y=10.0, shot=True, secs=9.0, goal=True),
            turnover(y=70.0, shot=False),
        ])
        out = league_totals(data)
        assert out["turnovers"] == 4
        assert out["shot_ending"] == 2
        assert out["goals"] == 1
        assert out["centre_rate"] == pytest.approx(0.5)
        assert out["wide_rate"] == pytest.approx(0.5)
        assert out["median_seconds"] == pytest.approx(7.0)