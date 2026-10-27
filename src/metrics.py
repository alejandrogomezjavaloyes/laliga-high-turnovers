"""Cálculos sobre los robos altos, sin nada de interfaz.

Separado de app.py a propósito: así se puede probar con tests normales,
sin arrancar Streamlit.

Datos: StatsBomb Open Data (https://github.com/statsbomb/open-data)
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

PITCH_LENGTH = 120.0
PITCH_WIDTH = 80.0

# 40 m sobre un campo real de ~105 m, en unidades StatsBomb.
HIGH_TURNOVER_X = PITCH_LENGTH - 40.0 * (PITCH_LENGTH / 105.0)

LANE_LOW = PITCH_WIDTH / 3
LANE_HIGH = PITCH_WIDTH * 2 / 3

DISTANCE_BANDS = [
    ("40-30 m", 74.3, 85.0),
    ("30-18 m", 85.0, 100.0),
    ("menos de 18 m", 100.0, 121.0),
]

EXPORT_DIR = Path(__file__).resolve().parent.parent / "data" / "export"


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de confianza de Wilson.

    Más fiable que el normal cuando la muestra es pequeña o la proporción
    se acerca a 0 o a 1, que es justo nuestro caso: 66-155 robos por equipo.
    """
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def load_turnovers(path: Path | None = None) -> pd.DataFrame:
    """Carga los robos altos y añade la columna de carril."""
    path = path or (EXPORT_DIR / "turnovers.csv")
    if not path.exists():
        raise FileNotFoundError(
            f"No se encuentra {path}. Ejecuta src/download.py, src/turnovers.py "
            "y src/export_dashboard.py para generarlo."
        )
    turnovers = pd.read_csv(path)
    turnovers["lane"] = turnovers["start_y"].map(lane_of)
    return turnovers


def lane_of(y: float) -> str:
    """Carril en el que cae una coordenada: centro o banda."""
    return "Centro" if LANE_LOW <= y < LANE_HIGH else "Bandas"


def summarise(turnovers: pd.DataFrame, by: str) -> pd.DataFrame:
    """Agrupa por una columna y calcula acierto, xG por robo e intervalo."""
    grouped = (
        turnovers.groupby(by)
        .agg(
            turnovers=("ended_in_shot", "size"),
            shot_ending=("ended_in_shot", "sum"),
            shots=("shots", "sum"),
            xg=("shot_xg", "sum"),
            goals=("is_goal", "sum"),
        )
        .reset_index()
    )
    grouped["shot_rate"] = grouped["shot_ending"] / grouped["turnovers"]
    grouped["xg_per_turnover"] = grouped["xg"] / grouped["turnovers"]

    bounds = [
        wilson_interval(int(k), int(n))
        for k, n in zip(grouped["shot_ending"], grouped["turnovers"])
    ]
    grouped["ci_low"] = [lo for lo, _ in bounds]
    grouped["ci_high"] = [hi for _, hi in bounds]
    return grouped


def by_distance(turnovers: pd.DataFrame) -> pd.DataFrame:
    """Acierto agrupado por franjas de distancia a la portería rival."""
    rows = []
    for name, low, high in DISTANCE_BANDS:
        band = turnovers[(turnovers["start_x"] >= low) & (turnovers["start_x"] < high)]
        n = len(band)
        k = int(band["ended_in_shot"].sum())
        lo, hi = wilson_interval(k, n)
        rows.append(
            {
                "band": name,
                "turnovers": n,
                "shot_ending": k,
                "shot_rate": k / n if n else 0.0,
                "xg_per_turnover": band["shot_xg"].sum() / n if n else 0.0,
                "ci_low": lo,
                "ci_high": hi,
            }
        )
    return pd.DataFrame(rows)


def league_totals(turnovers: pd.DataFrame) -> dict:
    """Cifras de cabecera de toda la liga."""
    n = len(turnovers)
    k = int(turnovers["ended_in_shot"].sum())
    lanes = summarise(turnovers, "lane").set_index("lane")
    seconds = turnovers["seconds_to_shot"].dropna()
    return {
        "turnovers": n,
        "shot_ending": k,
        "shot_rate": k / n if n else 0.0,
        "goals": int(turnovers["is_goal"].sum()),
        "xg": float(turnovers["shot_xg"].sum()),
        "median_seconds": float(seconds.median()) if len(seconds) else float("nan"),
        "centre_rate": float(lanes.loc["Centro", "shot_rate"]) if "Centro" in lanes.index else 0.0,
        "wide_rate": float(lanes.loc["Bandas", "shot_rate"]) if "Bandas" in lanes.index else 0.0,
    }


def zone_grid(turnovers: pd.DataFrame, cols: int = 5, rows: int = 5,
              min_count: int = 10) -> pd.DataFrame:
    """Rejilla sobre la zona de ataque, con el acierto de cada casilla.

    Las casillas con menos de `min_count` robos quedan con shot_rate nulo:
    con tan pocos datos el porcentaje no significa nada.
    """
    cell_w = (PITCH_LENGTH - HIGH_TURNOVER_X) / cols
    cell_h = PITCH_WIDTH / rows

    out = []
    for i in range(cols):
        for j in range(rows):
            x0 = HIGH_TURNOVER_X + i * cell_w
            y0 = j * cell_h
            # La última casilla de cada eje incluye su borde superior: hay robos
            # justo en la línea de banda (y = 80.0) que si no se perderían.
            last_col = i == cols - 1
            last_row = j == rows - 1
            inside = turnovers[
                (turnovers["start_x"] >= x0)
                & (
                    (turnovers["start_x"] <= x0 + cell_w)
                    if last_col
                    else (turnovers["start_x"] < x0 + cell_w)
                )
                & (turnovers["start_y"] >= y0)
                & (
                    (turnovers["start_y"] <= y0 + cell_h)
                    if last_row
                    else (turnovers["start_y"] < y0 + cell_h)
                )
            ]
            n = len(inside)
            k = int(inside["ended_in_shot"].sum())
            out.append(
                {
                    "x0": x0,
                    "y0": y0,
                    "width": cell_w,
                    "height": cell_h,
                    "turnovers": n,
                    "shot_ending": k,
                    "shot_rate": (k / n) if n >= min_count else float("nan"),
                }
            )
    return pd.DataFrame(out)