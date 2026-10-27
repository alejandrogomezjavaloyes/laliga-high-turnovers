"""Exporta los datos que alimentan el panel web.

Genera dos CSV ligeros en data/export/:
  - teams.csv       resumen por equipo (el que ya alimenta el panel)
  - turnovers.csv   un robo alto por fila, con su posicion en el campo

turnovers.csv es el que hace falta para dibujar los mapas de campo.

Datos: StatsBomb Open Data (https://github.com/statsbomb/open-data)
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from turnovers import (
    DATA_DIR,
    build_possessions,
    flag_high_turnovers,
    load_events,
    team_summary,
)

EXPORT_DIR = DATA_DIR / "export"

log = logging.getLogger("export")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    possessions_file = DATA_DIR / "possessions.parquet"
    if possessions_file.exists():
        log.info("Reutilizando %s", possessions_file.name)
        possessions = pd.read_parquet(possessions_file)
    else:
        log.info("No hay possessions.parquet, recalculando desde los eventos")
        possessions = flag_high_turnovers(build_possessions(load_events()))

    matches = pd.read_parquet(DATA_DIR / "matches.parquet")

    # 1) Resumen por equipo
    summary = team_summary(possessions, matches)
    summary_out = summary[
        ["team", "matches", "high_turnovers", "shot_ending", "shots", "xg", "goals"]
    ].copy()
    summary_out["xg"] = summary_out["xg"].round(3)
    summary_out.to_csv(EXPORT_DIR / "teams.csv", index=False)
    log.info("teams.csv: %d equipos", len(summary_out))

    # 2) Un robo alto por fila, para los mapas de campo
    high = possessions[possessions["is_high_turnover"]].copy()
    turnovers = high[
        [
            "match_id",
            "team",
            "start_x",
            "start_y",
            "start_type",
            "start_player",
            "ended_in_shot",
            "shots",
            "shot_xg",
            "is_goal",
            "seconds_to_shot",
        ]
    ].copy()

    turnovers["start_x"] = turnovers["start_x"].round(1)
    turnovers["start_y"] = turnovers["start_y"].round(1)
    turnovers["shot_xg"] = turnovers["shot_xg"].round(4)
    turnovers["seconds_to_shot"] = turnovers["seconds_to_shot"].round(0)

    turnovers.to_csv(EXPORT_DIR / "turnovers.csv", index=False)
    size_kb = (EXPORT_DIR / "turnovers.csv").stat().st_size / 1024
    log.info("turnovers.csv: %d robos altos (%.0f KB)", len(turnovers), size_kb)

    log.info("Exportado en %s", EXPORT_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())