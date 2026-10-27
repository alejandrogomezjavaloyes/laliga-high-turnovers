"""Descarga y cachea los eventos de LaLiga 2015/16 desde StatsBomb Open Data.

Cada partido se normaliza a un Parquet independiente en data/events/.
El script es idempotente: si el Parquet ya existe, no vuelve a descargarlo.

Datos: StatsBomb Open Data (https://github.com/statsbomb/open-data)
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

#DEFINIMOS LAS CONSTANTES INICIALES AL PRINCIPIO, QUE VAMOS A UTILIZAR DURANTE TODAS LAS FUNCIONES

BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"

# LaLiga 2015/16 (temporada completa, liberación de las 5 grandes ligas)
COMPETITION_ID = 11 #el id 11 se refiere a la liga dentro de los datos que organiza StatsBomb
SEASON_ID = 27 #el id 27 fija la temporada, en este caso va a ser la 15/16

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EVENTS_DIR = DATA_DIR / "events"

# Columnas que conservamos. Las que no existan en un partido se ignoran:
# StatsBomb solo incluye la clave cuando el evento la tiene.
KEEP_COLUMNS = [
    "id",
    "index",
    "period",
    "timestamp",
    "minute",
    "second",
    "duration",
    "possession",
    "possession_team.name",
    "play_pattern.name",
    "type.name",
    "team.name",
    "player.name",
    "position.name",
    "location",
    "under_pressure",
    "counterpress",
    "shot.statsbomb_xg",
    "shot.outcome.name",
    "shot.type.name",
    "pass.end_location",
    "pass.outcome.name",
    "carry.end_location",
    "duel.type.name",
    "duel.outcome.name",
    "interception.outcome.name",
    "ball_receipt.outcome.name",
]

log = logging.getLogger("download")


#Con esta función creamos una sesión HTTP que se reutiliza para todas las descargas
#esto sirve como buena práctica para no abrir una conexion TCP nueva por cada uno de los GET que  hagamos
def build_session() -> requests.Session:
    """Sesión HTTP reutilizable, para no abrir una conexión por fichero."""
    session = requests.Session()
    session.headers.update({"User-Agent": "laliga-high-turnovers/0.1 (proyecto educativo)"})
    return session


#Con esta función realizamos las peticiones GET con la libreria request a la url donde están los datos que hemos definido antes
def fetch_json(session: requests.Session, url: str, retries: int = 3):
    """GET con reintentos y espera incremental."""
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status() #lanza una excepción por si el servidor devuelve un 404 o un 500
            return response.json()
        except requests.RequestException as exc:
            if attempt == retries:
                raise
            wait = 2**attempt #espera 2 segundos, luego 4, luego 8, esto es por si el servidor está saturado dejar un poco de espacio entre solicitudes
            log.warning("Fallo en %s (intento %d/%d): %s. Reintento en %ds",
                        url, attempt, retries, exc, wait)
            time.sleep(wait)
    raise RuntimeError("inalcanzable")


def load_matches(session: requests.Session) -> pd.DataFrame:
    """Lista de partidos de la temporada, con marcador y equipos."""
    url = f"{BASE_URL}/matches/{COMPETITION_ID}/{SEASON_ID}.json"
    raw = fetch_json(session, url)
    matches = pd.json_normalize(raw) #convertimos el json anidado en una tabla plana

    columns = {
        "match_id": "match_id",
        "match_date": "match_date",
        "home_team.home_team_name": "home_team",
        "away_team.away_team_name": "away_team",
        "home_score": "home_score",
        "away_score": "away_score",
        "match_week": "match_week",
    }
    available = {src: dst for src, dst in columns.items() if src in matches.columns} 
    #en vez de asumir que todas las columnas existen, se queda con las que realmente están
    #si statsbomb cambiase algo mañana, mantenemos el script haciendolo duradero y que no se rompa
    return matches[list(available)].rename(columns=available).sort_values("match_id")


#Como statsBomb guarda las posiciones como una lista, por ejemplo: [110.0, 40.0]
#no puedes filtrar ni agrupar directamente, entonces con esta función la partimos en dos columnas numéricas
#que van a ser loc_x y loc_y
def split_location(frame: pd.DataFrame, column: str, prefix: str) -> pd.DataFrame:
    """Convierte una columna [x, y] en dos columnas numéricas.

    StatsBomb usa un campo de 120x80. Las coordenadas de tiro pueden traer
    un tercer valor (altura); aquí solo nos quedamos con x e y.
    """

    #las comprobaciones son necesarias porque no todos los eventos tienen posicion(por ej. un cambio)
    # y porque por ejemplo los tiros pueden traer tres valores en vez de dos(añaden altura), por eso no podemos
    #asumir siempre dos valores porque acabaría petando
    if column not in frame.columns:
        return frame

    def coord(value, index):
        if isinstance(value, (list, tuple)) and len(value) > index:
            return value[index]
        return None

    frame[f"{prefix}_x"] = frame[column].map(lambda v: coord(v, 0))
    frame[f"{prefix}_y"] = frame[column].map(lambda v: coord(v, 1))
    return frame.drop(columns=[column])


#Esta es la función central, se encarga de coger el JSON en crudo de un partido y lo deja listo para analizar
def normalize_events(raw: list, match_id: int) -> pd.DataFrame:
    """Aplana el JSON anidado de eventos y deja solo lo que vamos a usar."""
    events = pd.json_normalize(raw)
    events["match_id"] = match_id

    #también cubrimos la fiabilidad del script, ya que statbomb incluye un campo cuando el evento lo tiene
    #por ejemplo si hay un partido sin tarjetas rojas, la columna de expulsiones no existira, por eso no
    #podemos pedir una lista fija de columnas, iteramos sobre las columnas que hemos definido al inicio
    #y las que se encuentren en el evento las guardamos
    present = [c for c in KEEP_COLUMNS if c in events.columns] + ["match_id"]
    events = events[present].copy()

    events = split_location(events, "location", "loc")
    events = split_location(events, "pass.end_location", "pass_end")
    events = split_location(events, "carry.end_location", "carry_end")

    # Puntos en los nombres de columna complican las consultas más adelante.
    events.columns = [c.replace(".", "_") for c in events.columns] #cambia shot.statsbomb_xg por shot_statsbomb_xg

    # Segundo absoluto dentro del partido: necesario para encadenar eventos.
    events["abs_second"] = events["minute"] * 60 + events["second"]
    #como queremos saber si un robo acaba en tiro a los 10 segundos, necesitamos restar segundos y por
    #tanto el tiempo completo hay que tenerlo solo en segundos

    return events


def download_match(session: requests.Session, match_id: int, force: bool = False) -> str:
    """Descarga un partido y lo guarda como Parquet. Devuelve el estado."""
    target = EVENTS_DIR / f"{match_id}.parquet"

    #con esta linea solo va a descargar lo que falta, puedes relanzar por si falla el script y todo
    #lo descargado queda en cache y sigue por donde se quedo
    if target.exists() and not force:
        return "cacheado"

    raw = fetch_json(session, f"{BASE_URL}/events/{match_id}.json")
    events = normalize_events(raw, match_id)
    events.to_parquet(target, index=False, compression="snappy")
    return "descargado"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4,
                        help="descargas en paralelo (por defecto 4)")
    parser.add_argument("--limit", type=int, default=None,
                        help="descargar solo los N primeros partidos (para probar)")
    parser.add_argument("--force", action="store_true",
                        help="volver a descargar aunque exista el Parquet")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)

    session = build_session()

    log.info("Descargando lista de partidos...")
    matches = load_matches(session)
    matches.to_parquet(DATA_DIR / "matches.parquet", index=False)
    log.info("%d partidos en LaLiga 2015/16", len(matches))

    match_ids = matches["match_id"].tolist()
    if args.limit:
        match_ids = match_ids[: args.limit]

    counts = {"descargado": 0, "cacheado": 0, "error": 0}


    #con esta linea, lanza varias descargas a la vez, ya que en todo caso el cuello de botella
    #es la red y no la CPU
    with ThreadPoolExecutor(max_workers=args.workers) as pool:

        #cada tarea enviada devuelve un future, una promesa de resultado, los va devolviendo segun terminan
        #no en orden, y el diccionario sirve para saber a que partido corresponde cada uno cuando hay que reportar un error
        futures = {
            pool.submit(download_match, session, mid, args.force): mid
            for mid in match_ids
        }
        for done, future in enumerate(as_completed(futures), start=1):
            match_id = futures[future]

            #si un partido falla, se registra y se sigue con los demás, ya que lo contrario sería un mal diseño
            try:
                counts[future.result()] += 1
            except Exception as exc:
                counts["error"] += 1
                log.error("Partido %s: %s", match_id, exc)

            if done % 25 == 0 or done == len(futures):
                log.info("%d/%d partidos procesados", done, len(futures))

    log.info("Listo. Descargados: %d | En caché: %d | Errores: %d",
             counts["descargado"], counts["cacheado"], counts["error"])
    log.info("Parquet en %s", EVENTS_DIR)

    return 1 if counts["error"] else 0 #devuelve el código de salida del proceso, 0 si todo fue bien, 1 si hubo errores


if __name__ == "__main__":
    sys.exit(main())