"""Calcula high turnovers en LaLiga 2015/16 a partir de los eventos cacheados.

Definición (Opta / Stats Perform):
  - High turnover: recuperar el balón en juego dinámico a 40 m o menos de la
    portería rival.
  - Shot-ending high turnover: ese mismo robo acaba en tiro.

Aquí aproximamos la "secuencia" de Opta con la posesión de StatsBomb, que es la
unidad que trae el dato. Se documenta como limitación en el README.

Datos: StatsBomb Open Data (https://github.com/statsbomb/open-data)
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EVENTS_DIR = DATA_DIR / "events"

# El campo de StatsBomb mide 120x80 unidades, independientemente del estadio.
PITCH_LENGTH = 120.0

# 40 m sobre un campo real de ~105 m, llevados a unidades StatsBomb.
# 40 * (120 / 105) = 45.7 unidades desde la portería rival -> x >= 74.3
METRES_FROM_GOAL = 40.0
REAL_PITCH_METRES = 105.0
HIGH_TURNOVER_X = PITCH_LENGTH - METRES_FROM_GOAL * (PITCH_LENGTH / REAL_PITCH_METRES)

# Patrones de juego que cuentan como juego dinámico (no saque de banda, córner...).
OPEN_PLAY_PATTERNS = {"Regular Play", "From Counter"}

log = logging.getLogger("turnovers")


def load_events(limit: int | None = None) -> pd.DataFrame:
    """Lee todos los Parquet de partidos y los concatena en un solo DataFrame."""
    files = sorted(EVENTS_DIR.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(
            f"No hay Parquet en {EVENTS_DIR}. Ejecuta primero src/download.py"
        )
    if limit:
        files = files[:limit]

    log.info("Leyendo %d partidos...", len(files))
    events = pd.concat((pd.read_parquet(f) for f in files), ignore_index=True)
    log.info("%s eventos cargados", f"{len(events):,}")
    return events


def build_possessions(events: pd.DataFrame) -> pd.DataFrame:
    """Una fila por posesión: quién la tuvo, dónde empezó y si acabó en tiro."""
    events = events.sort_values(["match_id", "period", "abs_second", "index"])

    # El inicio de la posesión es el primer evento con posición del equipo que la
    # tiene. Se filtra por equipo porque el primer evento registrado puede ser una
    # acción del rival (una presión, un pase fallado).
    owned = events[
        (events["team_name"] == events["possession_team_name"])
        & events["loc_x"].notna()
    ]
    starts = (
        owned.groupby(["match_id", "possession"], as_index=False)
        .first()[
            [
                "match_id",
                "possession",
                "possession_team_name",
                "play_pattern_name",
                "type_name",
                "player_name",
                "loc_x",
                "loc_y",
                "abs_second",
                "period",
            ]
        ]
        .rename(
            columns={
                "possession_team_name": "team",
                "play_pattern_name": "play_pattern",
                "type_name": "start_type",
                "player_name": "start_player",
                "loc_x": "start_x",
                "loc_y": "start_y",
                "abs_second": "start_second",
            }
        )
    )

    # Tiros del equipo que tiene la posesión. Se excluyen los penaltis: no vienen
    # de una recuperación, distorsionarían la métrica.
    if "shot_type_name" in events.columns:
        not_penalty = events["shot_type_name"].ne("Penalty")
    else:
        not_penalty = pd.Series(True, index=events.index)

    shots = events[
        (events["type_name"] == "Shot")
        & (events["team_name"] == events["possession_team_name"])
        & not_penalty
    ].copy()
    shots["is_goal"] = shots["shot_outcome_name"] == "Goal"

    # Se agregan TODOS los tiros de la jugada, rechaces incluidos: una jugada con
    # disparo, rechace y gol vale más que una con un disparo flojo.
    # El tiempo se mide hasta el primero, porque eso es lo que mide la velocidad
    # de la transición, no cuánto dura el barullo posterior.
    shot_stats = (
        shots.sort_values(["match_id", "possession", "abs_second"])
        .groupby(["match_id", "possession"], as_index=False)
        .agg(
            shot_second=("abs_second", "first"),
            shots=("abs_second", "count"),
            shot_xg=("shot_statsbomb_xg", "sum"),
            first_shot_xg=("shot_statsbomb_xg", "first"),
            is_goal=("is_goal", "max"),
        )
    )

    possessions = starts.merge(shot_stats, on=["match_id", "possession"], how="left")
    possessions["ended_in_shot"] = possessions["shot_second"].notna()
    possessions["seconds_to_shot"] = possessions["shot_second"] - possessions["start_second"]
    possessions["shots"] = possessions["shots"].fillna(0).astype(int)
    possessions["shot_xg"] = possessions["shot_xg"].fillna(0.0)
    possessions["is_goal"] = possessions["is_goal"].fillna(False).astype(bool)

    return possessions


def flag_high_turnovers(
    possessions: pd.DataFrame, threshold_x: float = HIGH_TURNOVER_X
) -> pd.DataFrame:
    """Marca qué posesiones cumplen la definición de high turnover."""
    possessions = possessions.copy()
    possessions["is_open_play"] = possessions["play_pattern"].isin(OPEN_PLAY_PATTERNS)
    possessions["is_high"] = possessions["start_x"] >= threshold_x
    possessions["is_high_turnover"] = possessions["is_open_play"] & possessions["is_high"]
    return possessions


def team_summary(possessions: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    """Resumen por equipo: robos altos, cuántos acaban en tiro y xG generado."""
    high = possessions[possessions["is_high_turnover"]]

    summary = (
        high.groupby("team")
        .agg(
            high_turnovers=("possession", "count"),
            shot_ending=("ended_in_shot", "sum"),
            shots=("shots", "sum"),
            goals=("is_goal", "sum"),
            xg=("shot_xg", "sum"),
            median_seconds_to_shot=("seconds_to_shot", "median"),
        )
        .reset_index()
    )

    played = matches_played(matches)
    summary = summary.merge(played, on="team", how="left")

    summary["ht_per_match"] = summary["high_turnovers"] / summary["matches"]
    summary["shot_rate"] = summary["shot_ending"] / summary["high_turnovers"]
    summary["xg_per_turnover"] = summary["xg"] / summary["high_turnovers"]

    return summary.sort_values("ht_per_match", ascending=False).reset_index(drop=True)


def matches_played(matches: pd.DataFrame) -> pd.DataFrame:
    """Partidos jugados por equipo, contando local y visitante."""
    home = matches[["home_team"]].rename(columns={"home_team": "team"})
    away = matches[["away_team"]].rename(columns={"away_team": "team"})
    both = pd.concat([home, away], ignore_index=True)
    return both.value_counts("team").rename("matches").reset_index()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None,
                        help="usar solo los N primeros partidos (para probar)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    events = load_events(limit=args.limit)
    matches = pd.read_parquet(DATA_DIR / "matches.parquet")

    log.info("Umbral de high turnover: x >= %.1f (de 120)", HIGH_TURNOVER_X)

    possessions = build_possessions(events)
    possessions = flag_high_turnovers(possessions)
    log.info("%s posesiones, de las cuales %s son high turnovers",
             f"{len(possessions):,}",
             f"{int(possessions['is_high_turnover'].sum()):,}")

    possessions.to_parquet(DATA_DIR / "possessions.parquet", index=False)

    summary = team_summary(possessions, matches)
    summary.to_csv(DATA_DIR / "team_summary.csv", index=False)

    pd.set_option("display.width", 200, "display.max_columns", 30)
    print()
    print("High turnovers por partido (LaLiga 2015/16)")
    print(
        summary[["team", "matches", "high_turnovers", "ht_per_match",
                 "shot_ending", "shot_rate", "shots", "xg", "goals"]]
        .round(3)
        .to_string(index=False)
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())