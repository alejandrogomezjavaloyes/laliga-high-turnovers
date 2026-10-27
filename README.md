# Robos altos en LaLiga 2015/16

Dónde recuperan el balón los equipos en campo rival, y cuántos de esos robos
acaban en tiro. Pipeline reproducible sobre 1.295.354 eventos de StatsBomb Open
Data, con un panel interactivo en Streamlit.

**Panel en vivo:** laliga-high-turnovers.streamlit.app

![Mapa de robos altos](docs/pitch_all.png)

## El hallazgo

Un balón robado en el **carril central** acabó en tiro el **30,1%** de las veces.
Por las **bandas**, el **18,4%**. Los intervalos de confianza al 95% no se
solapan, así que la diferencia no es casualidad. Y sin embargo solo uno de cada
cinco robos altos ocurrió por el centro.

A nivel de equipo, en cambio, robar más no significa convertir más: la
correlación entre robos por partido y porcentaje de acierto es de **−0,02**. La
Real Sociedad fue el equipo que más robó en campo rival y el que peor lo
aprovechó; el Atlético robó un 23% menos y generó más del doble de ocasiones.

## Qué es un robo alto

Siguiendo la definición de Opta: **recuperar el balón en juego dinámico a 40
metros o menos de la portería rival**. Sobre el campo normalizado de StatsBomb
(120 × 80 unidades) el umbral cae en `x ≥ 74,3`:

```
HIGH_TURNOVER_X = 120 - 40 * (120 / 105)
```

## Cómo ejecutarlo

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python src/download.py          # descarga y cachea los 380 partidos (minutos)
python src/turnovers.py         # calcula los robos altos
python src/export_dashboard.py  # exporta los CSV del panel

streamlit run src/app.py        # abre el panel
```

Los CSV de `data/export/` vienen en el repositorio, así que **el panel arranca
sin descargar nada**. Los tres primeros pasos solo hacen falta para
regenerarlos o para cambiar de temporada.

## Estructura

```
src/
  download.py           ingesta: StatsBomb -> Parquet por partido
  turnovers.py          transformación: eventos -> posesiones -> robos altos
  metrics.py            cálculo puro (sin interfaz), testeable
  export_dashboard.py   exporta los CSV que consume el panel
  app.py                panel en Streamlit
data/
  events/*.parquet      caché de eventos (no versionado)
  export/*.csv          los dos CSV del panel (versionados)
tests/
  test_metrics.py
```

Las etapas **no se llaman entre sí**: se comunican a través de ficheros en
disco. Descargar es caro y depende de la red; analizar es barato y se itera
muchas veces. Separarlas permite repetir el análisis sin volver a descargar, y
que un fallo en una etapa no destruya el trabajo de la anterior.

## Decisiones de diseño

**Parquet, no JSON.** El JSON de un partido ocupa varios MB y hay 380. En
Parquet con compresión ocupa una fracción y se lee mucho más rápido.

**Un fichero por partido.** El proceso es idempotente: si falla en el partido
200, se relanza y continúa desde ahí sin repetir trabajo.

**Intervalos de Wilson, no normales.** Con muestras de 66 a 155 robos por
equipo y proporciones cercanas a 0,2, el intervalo normal da cotas
irreales. Wilson se comporta bien en ese rango.

**Loader propio en vez de `statsbombpy`.** La librería oficial habría sido más
corta, pero el caché, los reintentos y el formato de salida son parte de lo que
este repositorio quiere mostrar.

## Limitaciones

- **Posesiones, no secuencias.** Opta define la métrica sobre *secuencias*;
  StatsBomb da *posesiones*, que son más gruesas. Por eso los totales salen por
  debajo de las cifras que publica Opta. No ha sido posible contrastarlos con
  sus datos de LaLiga 2015/16, que no son públicos.
- **xG sumado por jugada.** Se suman todos los disparos de la posesión,
  rechaces incluidos. Es práctica habitual, pero sobreestima algo la
  probabilidad real de gol: si el primer disparo entra, el segundo no existe.
- **Muestras pequeñas.** Las diferencias en la zona media de la tabla no son
  distinguibles entre sí. Solo los extremos lo son.
- **Una sola temporada.** 2015/16 es la temporada completa de LaLiga que
  StatsBomb libera. Los patrones pueden no generalizar a otras.

## Tests

```bash
python -m pytest tests/ -v
```

## Datos

[StatsBomb Open Data](https://github.com/statsbomb/open-data). Este proyecto no
está afiliado a StatsBomb ni a LaLiga.
