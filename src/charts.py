"""Gráficos del panel, en Plotly.

Cada función recibe un DataFrame ya calculado y devuelve una figura. No hay
cálculo aquí: eso vive en metrics.py.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from metrics import (
    HIGH_TURNOVER_X,
    LANE_HIGH,
    LANE_LOW,
    PITCH_LENGTH,
    PITCH_WIDTH,
    zone_grid,
)
from theme import ACCENT, COOL, HEAT, INK, LINE, MUTED, PANEL, axis, plot_layout

VIEW_X0 = 68.0
GOAL_GAP = 5.0


def _pitch_shapes() -> list[dict]:
    """Líneas del campo, en vertical y con la portería arriba.

    En pantalla el eje X es el ANCHO del campo (0-80) y el eje Y es el LARGO
    (68-120). Es la orientación habitual para mapas del último tercio.
    """
    line = dict(color=INK, width=1.4)
    soft = dict(color=MUTED, width=1, dash="dot")

    def seg(y0, x0, y1, x1, style=None):
        return dict(type="line", x0=y0, y0=x0, x1=y1, y1=x1,
                    line=style or line, layer="above")

    return [
        # Bandas y línea de fondo
        seg(0, VIEW_X0, 0, PITCH_LENGTH),
        seg(PITCH_WIDTH, VIEW_X0, PITCH_WIDTH, PITCH_LENGTH),
        seg(0, PITCH_LENGTH, PITCH_WIDTH, PITCH_LENGTH),
        # Área grande
        seg(18, 102, 62, 102),
        seg(18, 102, 18, 120),
        seg(62, 102, 62, 120),
        # Área pequeña
        seg(30, 114, 50, 114),
        seg(30, 114, 30, 120),
        seg(50, 114, 50, 120),
        # Portería, asomando por detrás de la línea de fondo
        seg(36, 120, 36, 123),
        seg(44, 120, 44, 123),
        seg(36, 123, 44, 123),
        # Umbral de los 40 m
        seg(0, HIGH_TURNOVER_X, PITCH_WIDTH, HIGH_TURNOVER_X,
            dict(color=ACCENT, width=1.4, dash="dash")),
        # Carriles
        seg(LANE_LOW, HIGH_TURNOVER_X, LANE_LOW, PITCH_LENGTH, soft),
        seg(LANE_HIGH, HIGH_TURNOVER_X, LANE_HIGH, PITCH_LENGTH, soft),
    ]


def _pitch_frame(fig: go.Figure, height: int) -> go.Figure:
    fig.add_shape(
        type="circle", x0=39.2, y0=107.2, x1=40.8, y1=108.8,
        fillcolor=INK, line=dict(width=0), layer="above",
    )
    fig.add_annotation(
        x=1.5, y=HIGH_TURNOVER_X - 1.5, text="40 m", showarrow=False,
        font=dict(family="JetBrains Mono, monospace", size=11, color=ACCENT),
        xanchor="left", yanchor="top",
    )
    fig.update_layout(
        **plot_layout(height=height, shapes=_pitch_shapes()),
        xaxis=dict(range=[-3, PITCH_WIDTH + 3], visible=False, fixedrange=True),
        yaxis=dict(
            range=[VIEW_X0 - 2, PITCH_LENGTH + GOAL_GAP + 1],
            visible=False, fixedrange=True,
            scaleanchor="x", scaleratio=1,
        ),
    )
    return fig


def pitch_heatmap(turnovers: pd.DataFrame, height: int = 680) -> go.Figure:
    """Mapa de calor por casillas: porcentaje que acaba en tiro."""
    cells = zone_grid(turnovers)
    cols = sorted(cells["y0"].unique())
    rows = sorted(cells["x0"].unique())

    z, text, custom = [], [], []
    for x0 in rows:
        z_row, t_row, c_row = [], [], []
        for y0 in cols:
            cell = cells[(cells["x0"] == x0) & (cells["y0"] == y0)].iloc[0]
            rate = cell["shot_rate"]
            z_row.append(None if pd.isna(rate) else rate)
            t_row.append("" if pd.isna(rate) else f"{rate:.0%}")
            c_row.append([int(cell["turnovers"]), int(cell["shot_ending"])])
        z.append(z_row)
        text.append(t_row)
        custom.append(c_row)

    cell_w = cells["height"].iloc[0]
    cell_h = cells["width"].iloc[0]

    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=[y0 + cell_w / 2 for y0 in cols],
            y=[x0 + cell_h / 2 for x0 in rows],
            text=text,
            customdata=custom,
            texttemplate="%{text}",
            textfont=dict(family="Archivo, sans-serif", size=14, color=INK),
            colorscale=HEAT,
            showscale=False,
            xgap=2,
            ygap=2,
            hovertemplate=(
                "<b>%{text} acaba en tiro</b><br>"
                "%{customdata[0]} robos en la zona<br>"
                "%{customdata[1]} acabaron en tiro<extra></extra>"
            ),
        )
    )
    return _pitch_frame(fig, height)


def pitch_scatter(turnovers: pd.DataFrame, team: str, height: int = 680) -> go.Figure:
    """Un punto por robo del equipo elegido."""
    rows = turnovers[turnovers["team"] == team]
    fig = go.Figure()

    for subset, colour, size, name in (
        (rows[~rows["ended_in_shot"]], COOL, 9, "No acabó en tiro"),
        (rows[rows["ended_in_shot"]], ACCENT, 12, "Acabó en tiro"),
    ):
        fig.add_trace(
            go.Scatter(
                x=subset["start_y"],
                y=subset["start_x"],
                mode="markers",
                name=name,
                marker=dict(
                    size=size, color=colour,
                    line=dict(width=1, color=PANEL),
                    opacity=0.9 if colour == ACCENT else 0.6,
                ),
                customdata=subset[["start_player", "start_type", "seconds_to_shot", "shot_xg"]],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "%{customdata[1]}<br>"
                    "%{customdata[2]:.0f} s hasta el tiro · %{customdata[3]:.3f} xG"
                    "<extra></extra>"
                ),
            )
        )

    fig = _pitch_frame(fig, height)
    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0,
            font=dict(size=12, color=MUTED), bgcolor="rgba(0,0,0,0)",
        ),
    )
    return fig


def interval_bars(frame: pd.DataFrame, label_col: str, highlight: set[str],
                  height: int | None = None) -> go.Figure:
    """Punto con bigotes: la proporción y su intervalo de confianza."""
    data = frame.sort_values("shot_rate")
    height = height or max(220, 34 * len(data) + 90)
    colours = [ACCENT if v in highlight else COOL for v in data[label_col]]

    fig = go.Figure()
    for (_, row), colour in zip(data.iterrows(), colours):
        fig.add_shape(
            type="line", x0=row["ci_low"], x1=row["ci_high"],
            y0=row[label_col], y1=row[label_col],
            line=dict(color=colour, width=3), opacity=0.45, layer="below",
        )

    fig.add_trace(
        go.Scatter(
            x=data["shot_rate"],
            y=data[label_col],
            mode="markers",
            marker=dict(size=12, color=colours, line=dict(width=1.5, color=PANEL)),
            customdata=data[["turnovers", "shot_ending", "ci_low", "ci_high"]],
            hovertemplate=(
                "<b>%{y}</b><br>"
                "%{x:.1%} acaba en tiro<br>"
                "intervalo %{customdata[2]:.1%} – %{customdata[3]:.1%}<br>"
                "%{customdata[1]} de %{customdata[0]} robos<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        **plot_layout(height=height, margin=dict(l=10, r=20, t=16, b=40)),
        xaxis=axis(tickformat=".0%", title=dict(text="Robos que acaban en tiro")),
        yaxis=axis(gridcolor="rgba(0,0,0,0)",
                   tickfont=dict(color=INK, size=12)),
    )
    return fig


def volume_vs_rate(teams: pd.DataFrame, matches: int = 38, height: int = 520) -> go.Figure:
    """Dispersión: robos por partido frente a porcentaje de acierto."""
    data = teams.copy()
    data["per_match"] = data["turnovers"] / matches
    best = data.loc[data["shot_rate"].idxmax(), "team"]
    worst = data.loc[data["shot_rate"].idxmin(), "team"]
    key = {best, worst}

    colours = [ACCENT if t in key else COOL for t in data["team"]]
    sizes = [20 if t in key else 14 for t in data["team"]]

    fig = go.Figure(
        go.Scatter(
            x=data["per_match"],
            y=data["shot_rate"],
            mode="markers+text",
            text=data["team"],
            textposition="top center",
            textfont=dict(
                size=11,
                color=[INK if t in key else MUTED for t in data["team"]],
            ),
            marker=dict(size=sizes, color=colours, line=dict(width=1.5, color=PANEL)),
            customdata=data[["turnovers", "shot_ending", "goals", "xg"]],
            hovertemplate=(
                "<b>%{text}</b><br>"
                "%{x:.2f} robos por partido<br>"
                "%{y:.1%} acaba en tiro<br>"
                "%{customdata[2]} goles · %{customdata[3]:.2f} xG<extra></extra>"
            ),
        )
    )

    mean_rate = data["shot_ending"].sum() / data["turnovers"].sum()
    fig.add_hline(y=mean_rate, line=dict(color=MUTED, width=1, dash="dot"),
                  annotation_text=f"media {mean_rate:.1%}",
                  annotation_position="right",
                  annotation_font=dict(size=11, color=MUTED))

    fig.update_layout(
        **plot_layout(height=height, margin=dict(l=10, r=20, t=24, b=46)),
        xaxis=axis(title=dict(text="Robos altos por partido")),
        yaxis=axis(tickformat=".0%", title=dict(text="Robos que acaban en tiro")),
    )
    return fig


def finishing_bars(teams: pd.DataFrame, height: int | None = None) -> go.Figure:
    """Barras a ambos lados del cero: goles menos xG."""
    data = teams.copy()
    data["diff"] = data["goals"] - data["xg"]
    data = data.sort_values("diff")
    height = height or max(260, 26 * len(data) + 90)

    colours = [ACCENT if d >= 2 else COOL for d in data["diff"]]

    fig = go.Figure(
        go.Bar(
            x=data["diff"],
            y=data["team"],
            orientation="h",
            marker=dict(color=colours, line=dict(width=0)),
            customdata=data[["goals", "xg"]],
            hovertemplate=(
                "<b>%{y}</b><br>"
                "%{customdata[0]} goles con %{customdata[1]:.2f} xG<br>"
                "%{x:+.2f} sobre lo esperado<extra></extra>"
            ),
        )
    )
    fig.add_vline(x=0, line=dict(color=LINE, width=1.5))

    fig.update_layout(
        **plot_layout(height=height, margin=dict(l=10, r=20, t=16, b=40),
                      bargap=0.35),
        xaxis=axis(title=dict(text="Goles por encima o por debajo del xG")),
        yaxis=axis(gridcolor="rgba(0,0,0,0)", tickfont=dict(color=INK, size=12)),
    )
    return fig


def distance_bars(bands: pd.DataFrame, height: int = 260) -> go.Figure:
    """Acierto por franja de distancia a la portería."""
    data = bands.iloc[::-1]
    colours = [ACCENT if i == len(data) - 1 else COOL for i in range(len(data))]

    fig = go.Figure(
        go.Bar(
            x=data["shot_rate"],
            y=data["band"],
            orientation="h",
            marker=dict(color=colours, line=dict(width=0)),
            text=[f"{v:.1%}" for v in data["shot_rate"]],
            textposition="outside",
            textfont=dict(size=12, color=INK),
            customdata=data[["turnovers", "xg_per_turnover"]],
            hovertemplate=(
                "<b>%{y}</b><br>"
                "%{x:.1%} acaba en tiro<br>"
                "%{customdata[0]} robos · %{customdata[1]:.3f} xG por robo"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        **plot_layout(height=height, margin=dict(l=10, r=50, t=16, b=40),
                      bargap=0.45),
        xaxis=axis(tickformat=".0%", range=[0, data["shot_rate"].max() * 1.3]),
        yaxis=axis(gridcolor="rgba(0,0,0,0)", tickfont=dict(color=INK, size=12)),
    )
    return fig