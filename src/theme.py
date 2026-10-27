"""Identidad visual del panel: paleta, tipografías y estilos compartidos.

Todo lo visual vive aquí para que app.py se ocupe solo de la estructura.
"""

from __future__ import annotations

# Paleta: verde profundo de césped en sombra, cobre para lo que importa,
# azul silicio para lo secundario.
BG = "#0F2620"
PANEL = "#16332B"
PANEL_SOFT = "#1B3C32"
LINE = "#24513F"
INK = "#EDEBE3"
MUTED = "#8FA99D"
ACCENT = "#D4924F"
ACCENT_SOFT = "#8A5E33"
COOL = "#9DB4C0"
GOOD = "#7FB069"

# Rampa del mapa de calor: del fondo al cobre.
HEAT = [
    [0.00, "#16332B"],
    [0.25, "#45402F"],
    [0.50, "#7A5B36"],
    [0.75, "#B07B41"],
    [1.00, "#E8A75C"],
]

FONT_URL = (
    "https://fonts.googleapis.com/css2"
    "?family=Archivo:wght@400;500;600;700;800"
    "&family=JetBrains+Mono:wght@400;500"
    "&display=swap"
)

CSS = f"""
<style>
@import url('{FONT_URL}');

html, body, [class*="css"] {{
    font-family: 'Archivo', system-ui, sans-serif;
}}

/* El modo ancho de Streamlit estira el contenido en monitores grandes y lo
   deja disperso. Un maximo lo mantiene compuesto. */
.block-container {{
    max-width: 1180px;
    padding-top: 2.2rem;
    padding-bottom: 3rem;
}}

.stApp {{
    background:
        radial-gradient(1200px 600px at 20% -10%, #17382F 0%, transparent 60%),
        {BG};
}}

/* Cabecera */
.hero {{ padding: 0.5rem 0 1.75rem; }}
.hero-eyebrow {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem; letter-spacing: 0.18em; text-transform: uppercase;
    color: {ACCENT}; margin-bottom: 0.9rem;
}}
.hero-title {{
    font-size: clamp(2rem, 4.5vw, 3.1rem); font-weight: 800;
    line-height: 1.03; letter-spacing: -0.02em; color: {INK};
    margin: 0 0 0.85rem; max-width: 20ch; text-wrap: balance;
}}
.hero-lede {{
    font-size: 1.02rem; line-height: 1.55; color: {MUTED};
    max-width: 62ch; margin: 0;
}}
.hero-lede b {{ color: {INK}; font-weight: 600; }}

/* Tarjetas de cifra */
.kpi-row {{ display: grid; gap: 0.85rem; grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr)); }}
.kpi {{
    background: {PANEL}; border: 1px solid {LINE};
    border-radius: 14px; padding: 1.1rem 1.15rem;
    position: relative; overflow: hidden;
}}
.kpi::before {{
    content: ''; position: absolute; inset: 0 auto 0 0; width: 3px;
    background: {ACCENT}; opacity: 0.85;
}}
.kpi-label {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.66rem; letter-spacing: 0.14em; text-transform: uppercase;
    color: {MUTED}; margin-bottom: 0.55rem;
}}
.kpi-value {{
    font-size: 2.15rem; font-weight: 700; line-height: 1;
    color: {INK}; font-variant-numeric: tabular-nums;
}}
.kpi-value.accent {{ color: {ACCENT}; }}
.kpi-note {{ font-size: 0.78rem; color: {MUTED}; margin-top: 0.5rem; }}

/* Secciones */
.section-head {{ margin: 2.2rem 0 0.9rem; }}
.section-title {{
    font-size: 1.32rem; font-weight: 700; color: {INK};
    margin: 0 0 0.35rem; letter-spacing: -0.01em;
}}
.section-note {{
    font-size: 0.87rem; line-height: 1.5; color: {MUTED};
    max-width: 68ch; margin: 0;
}}
.section-note b {{ color: {INK}; font-weight: 600; }}

/* Caja de hallazgo */
.finding {{
    background: linear-gradient(135deg, {PANEL_SOFT}, {PANEL});
    border: 1px solid {LINE}; border-left: 3px solid {ACCENT};
    border-radius: 14px; padding: 1.25rem 1.4rem; margin: 1.2rem 0;
}}
.finding-title {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.66rem; letter-spacing: 0.14em; text-transform: uppercase;
    color: {ACCENT}; margin-bottom: 0.6rem;
}}
.finding-body {{ font-size: 1rem; line-height: 1.6; color: {INK}; margin: 0; }}
.finding-body b {{ color: {ACCENT}; font-weight: 700; }}

/* Pestanas */
.stTabs [data-baseweb="tab-list"] {{ gap: 0.4rem; border-bottom: 1px solid {LINE}; }}
.stTabs [data-baseweb="tab"] {{
    background: transparent; border: none; border-radius: 8px 8px 0 0;
    padding: 0.65rem 1.1rem; color: {MUTED}; font-weight: 500; font-size: 0.93rem;
}}
.stTabs [aria-selected="true"] {{ background: {PANEL}; color: {INK}; }}

/* Barra lateral */
section[data-testid="stSidebar"] {{ background: {PANEL}; border-right: 1px solid {LINE}; }}
section[data-testid="stSidebar"] .sidebar-title {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.66rem; letter-spacing: 0.14em; text-transform: uppercase;
    color: {ACCENT}; margin-bottom: 0.3rem;
}}

/* Tabla */
[data-testid="stDataFrame"] {{ border: 1px solid {LINE}; border-radius: 12px; }}

/* Pie */
.footnote {{
    font-size: 0.8rem; line-height: 1.6; color: {MUTED};
    border-top: 1px solid {LINE}; padding-top: 1.1rem; margin-top: 2.2rem;
}}
.footnote b {{ color: {INK}; font-weight: 600; }}
.footnote p {{ margin: 0 0 0.6rem; }}

#MainMenu, footer {{ visibility: hidden; }}
</style>
"""


def plot_layout(height: int = 420, **extra) -> dict:
    """Capa base común a todos los gráficos."""
    layout = dict(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Archivo, sans-serif", size=13, color=INK),
        margin=dict(l=10, r=10, t=10, b=10),
        hoverlabel=dict(
            bgcolor=PANEL,
            bordercolor=LINE,
            font=dict(family="Archivo, sans-serif", size=12, color=INK),
        ),
        showlegend=False,
    )
    layout.update(extra)
    return layout


def axis(**extra) -> dict:
    """Eje con rejilla discreta, del color de la paleta."""
    base = dict(
        gridcolor=LINE,
        gridwidth=1,
        zeroline=False,
        linecolor=LINE,
        tickfont=dict(color=MUTED, size=11),
        title=dict(font=dict(color=MUTED, size=12)),
    )
    base.update(extra)
    return base