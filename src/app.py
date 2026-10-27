"""Panel de robos altos en LaLiga 2015/16.

Se lanza con:
    streamlit run src/app.py

Lee los CSV de data/export/, que genera src/export_dashboard.py.
El cálculo vive en metrics.py, los gráficos en charts.py y el estilo en
theme.py; aquí solo queda la estructura de la página.

Datos: StatsBomb Open Data (https://github.com/statsbomb/open-data)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from charts import (  # noqa: E402
    distance_bars,
    finishing_bars,
    interval_bars,
    pitch_heatmap,
    pitch_scatter,
    volume_vs_rate,
)
from metrics import (  # noqa: E402
    HIGH_TURNOVER_X,
    by_distance,
    league_totals,
    load_turnovers,
    summarise,
)
from theme import CSS  # noqa: E402

st.set_page_config(
    page_title="Robos altos · LaLiga 2015/16",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

PLOT_CONFIG = {"displayModeBar": False, "scrollZoom": False}


@st.cache_data
def get_turnovers() -> pd.DataFrame:
    return load_turnovers()


def thousands(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def kpi(label: str, value: str, note: str, accent: bool = False) -> str:
    cls = "kpi-value accent" if accent else "kpi-value"
    return (
        f'<div class="kpi"><div class="kpi-label">{label}</div>'
        f'<div class="{cls}">{value}</div>'
        f'<div class="kpi-note">{note}</div></div>'
    )


def section(title: str, note: str) -> None:
    st.markdown(
        f'<div class="section-head"><div class="section-title">{title}</div>'
        f'<p class="section-note">{note}</p></div>',
        unsafe_allow_html=True,
    )


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)

    try:
        turnovers = get_turnovers()
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()

    totals = league_totals(turnovers)
    teams = summarise(turnovers, "team")
    lanes = summarise(turnovers, "lane")
    bands = by_distance(turnovers)

    best = teams.loc[teams["shot_rate"].idxmax(), "team"]
    worst = teams.loc[teams["shot_rate"].idxmin(), "team"]
    centre_share = (turnovers["lane"] == "Centro").mean()
    ratio = totals["centre_rate"] / totals["wide_rate"]

    # ---------------------------------------------------------------- barra lateral
    with st.sidebar:
        st.markdown('<div class="sidebar-title">Filtro</div>', unsafe_allow_html=True)
        options = ["Todos los equipos"] + sorted(turnovers["team"].unique())
        choice = st.selectbox("Equipo", options, label_visibility="collapsed")
        team = None if choice == "Todos los equipos" else choice

        st.markdown("---")
        st.markdown('<div class="sidebar-title">Qué es un robo alto</div>',
                    unsafe_allow_html=True)
        st.caption(
            "Recuperar el balón en juego dinámico a 40 metros o menos de la "
            "portería rival, según la definición de Opta. Sobre el campo "
            f"normalizado de StatsBomb el umbral cae en x ≥ {HIGH_TURNOVER_X:.1f} "
            "de 120."
        )

        st.markdown("---")
        st.markdown('<div class="sidebar-title">Alcance</div>', unsafe_allow_html=True)
        st.caption(
            f"380 partidos · 1.295.354 eventos · "
            f"{thousands(totals['turnovers'])} robos altos · 20 equipos."
        )

    # ---------------------------------------------------------------- cabecera
    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-eyebrow">LaLiga 2015/16 · StatsBomb Open Data</div>
          <h1 class="hero-title">Dónde robas importa más que cuánto robas</h1>
          <p class="hero-lede">
            Un balón recuperado en el <b>carril central</b> acabó en tiro el
            <b>{totals['centre_rate']:.1%}</b> de las veces. Por las bandas,
            el <b>{totals['wide_rate']:.1%}</b>. Y sin embargo solo
            <b>{centre_share:.0%}</b> de los robos altos ocurrió por el centro.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="kpi-row">'
        + kpi("Robos en campo rival", thousands(totals["turnovers"]),
              "380 partidos, temporada completa")
        + kpi("Acierto por el centro", f"{totals['centre_rate']:.1%}",
              f"{thousands(int((turnovers['lane'] == 'Centro').sum()))} robos", accent=True)
        + kpi("Acierto por las bandas", f"{totals['wide_rate']:.1%}",
              f"{thousands(int((turnovers['lane'] == 'Bandas').sum()))} robos")
        + kpi("Tardan en rematar", f"{totals['median_seconds']:.0f} s",
              "mediana hasta el primer tiro")
        + "</div>",
        unsafe_allow_html=True,
    )

    tab_map, tab_teams, tab_data = st.tabs(
        ["  El mapa  ", "  Los equipos  ", "  Los datos  "]
    )

    # ---------------------------------------------------------------- mapa
    with tab_map:
        if team is None:
            section(
                "El mapa de los robos",
                "Campo de ataque, portería arriba. La línea discontinua marca los "
                "40 metros: a partir de ahí un robo cuenta como robo alto. Cada "
                "casilla se colorea por el porcentaje que acaba en tiro. Las que "
                "tienen menos de 10 robos se dejan en blanco: con tan pocos datos "
                "el porcentaje no significa nada.",
            )
            st.plotly_chart(pitch_heatmap(turnovers), use_container_width=True,
                            config=PLOT_CONFIG)
        else:
            rows = turnovers[turnovers["team"] == team]
            shots = int(rows["ended_in_shot"].sum())
            rate = shots / len(rows) if len(rows) else 0
            section(
                f"Los robos del {team}",
                f"Cada punto es un robo alto. En naranja, los que acabaron en tiro. "
                f"<b>{len(rows)} robos, {shots} con tiro ({rate:.1%})</b>. Las líneas "
                "de puntos separan el carril central de las bandas.",
            )
            st.plotly_chart(pitch_scatter(turnovers, team), use_container_width=True,
                            config=PLOT_CONFIG)

        st.markdown(
            f"""
            <div class="finding">
              <div class="finding-title">El hallazgo</div>
              <p class="finding-body">
                Robar por el centro convierte <b>{ratio:.2f} veces más</b> que robar
                por las bandas, y los intervalos de confianza no se solapan: la
                diferencia no es casualidad. Pero solo uno de cada cinco robos altos
                ocurre ahí.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        left, right = st.columns(2, gap="large")
        with left:
            section(
                "Centro frente a bandas",
                "Porcentaje que acaba en tiro, con su intervalo de confianza del 95%.",
            )
            st.plotly_chart(interval_bars(lanes, "lane", {"Centro"}, height=240),
                            use_container_width=True, config=PLOT_CONFIG)
        with right:
            section(
                "Cuanto más cerca, mejor",
                "Los mismos robos, agrupados por distancia a la portería rival.",
            )
            st.plotly_chart(distance_bars(bands), use_container_width=True,
                            config=PLOT_CONFIG)

    # ---------------------------------------------------------------- equipos
    with tab_teams:
        corr = (teams["turnovers"] / 38).corr(teams["shot_rate"])
        section(
            "Volumen frente a acierto",
            "Cada punto es un equipo. A la derecha, los que más roban; arriba, los "
            "que más convierten. Si una cosa llevara a la otra, los puntos formarían "
            f"una diagonal. No la forman: la correlación es de <b>{corr:.2f}</b>.",
        )
        st.plotly_chart(volume_vs_rate(teams), use_container_width=True,
                        config=PLOT_CONFIG)

        st.markdown(
            f"""
            <div class="finding">
              <div class="finding-title">Los dos extremos</div>
              <p class="finding-body">
                El <b>{worst}</b> fue el equipo que más robó en campo rival de toda
                LaLiga y el que peor lo aprovechó. El <b>{best}</b> robó bastante
                menos y generó más del doble de ocasiones.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        section(
            "Qué diferencias son reales",
            "Con entre 66 y 155 robos por equipo, muchas diferencias son ruido. Solo "
            "cuando dos intervalos no se solapan puede decirse que un equipo es "
            "mejor que otro.",
        )
        st.plotly_chart(interval_bars(teams, "team", {best, worst}),
                        use_container_width=True, config=PLOT_CONFIG)

        section(
            "Goles frente a lo esperado",
            "Diferencia entre los goles marcados tras un robo alto y el xG acumulado "
            "de esos disparos. A la derecha, los que remataron mejor de lo que "
            "decían sus ocasiones.",
        )
        st.plotly_chart(finishing_bars(teams), use_container_width=True,
                        config=PLOT_CONFIG)

    # ---------------------------------------------------------------- datos
    with tab_data:
        section("Todos los equipos", "Pulsa una cabecera para ordenar.")
        table = teams[
            ["team", "turnovers", "shot_ending", "shot_rate", "shots",
             "xg", "goals", "xg_per_turnover"]
        ].sort_values("turnovers", ascending=False)
        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
            height=min(760, 38 * len(table) + 48),
            column_config={
                "team": "Equipo",
                "turnovers": st.column_config.NumberColumn("Robos"),
                "shot_ending": st.column_config.NumberColumn("Con tiro"),
                "shot_rate": st.column_config.ProgressColumn(
                    "% acierto", format="%.1f%%", min_value=0.0,
                    max_value=float(table["shot_rate"].max()),
                ),
                "shots": st.column_config.NumberColumn("Tiros"),
                "xg": st.column_config.NumberColumn("xG", format="%.2f"),
                "goals": st.column_config.NumberColumn("Goles"),
                "xg_per_turnover": st.column_config.NumberColumn(
                    "xG por robo", format="%.3f"),
            },
        )

        st.download_button(
            "Descargar los robos en CSV",
            data=turnovers.to_csv(index=False).encode("utf-8"),
            file_name="high_turnovers_laliga_201516.csv",
            mime="text/csv",
        )

        section("Método y limitaciones", "")
        st.markdown(
            f"""
**Cómo está calculado.** A partir de 1.295.354 eventos de los 380 partidos de
LaLiga 2015/16. Se excluyen los penaltis. El xG suma todos los disparos de la
jugada, rechaces incluidos, lo que sobreestima algo la probabilidad real de gol
porque esos disparos no son independientes.

**Una aproximación.** Opta define la métrica sobre *secuencias*; StatsBomb da
*posesiones*, que son más gruesas. Por eso los totales salen por debajo de las
cifras que publica Opta, y no ha sido posible contrastarlos con sus datos de
LaLiga 2015/16, que no son públicos.

**Un matiz importante.** A nivel de liga el centro convierte mucho más que las
bandas, pero eso no explica qué equipos convierten mejor: la correlación entre
el porcentaje de robos por el centro y el acierto de cada equipo es de 0,04. De
hecho el {best}, el que mejor convierte, es el que menos roba por el centro.

**Intervalos de Wilson.** Con muestras de 66 a 155 robos y proporciones
cercanas a 0,2, el intervalo normal da cotas irreales. Wilson se comporta bien
en ese rango.
            """
        )

    st.markdown(
        """
        <div class="footnote">
          <p><b>Datos:</b> StatsBomb Open Data. Este proyecto no está afiliado a
          StatsBomb ni a LaLiga.</p>
          <p>Alejandro Gómez Javaloyes · Ciencia e Ingeniería de Datos,
          Universidad de Murcia</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()