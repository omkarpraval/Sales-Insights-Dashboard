"""
Sales Analysis Dashboard — Dash + Plotly + MongoDB (Superstore-style data).
"""
from __future__ import annotations

from pymongo import MongoClient
import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# -----------------------------
# THEME (matches assets/style.css)
# -----------------------------
CHART_TEMPLATE = "plotly_dark"
CHART_HEIGHT = 440
CHART_HEIGHT_SM = 400
COLORWAY = ["#38bdf8", "#818cf8", "#34d399", "#fbbf24", "#f472b6", "#94a3b8"]

# Shared Plotly mode bar: fewer icons, less clash with titles
GRAPH_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}

GRAPH_STYLE = {"width": "100%", "minHeight": "440px"}


def _fig_layout(
    fig,
    title: str,
    height: int = CHART_HEIGHT,
    *,
    legend_below: bool = True,
    show_legend: bool = True,
    extra_bottom: int = 0,
    extra_right: int = 0,
    extra_top: int = 0,
) -> None:
    """Center title below mode bar; optional legend under plot to avoid title overlap."""
    legend_h = 78 if (legend_below and show_legend) else 0
    bottom_margin = 44 + legend_h + extra_bottom
    top_margin = 92 + extra_top
    fig.update_layout(
        template=CHART_TEMPLATE,
        title=dict(
            text=title,
            x=0.5,
            xanchor="center",
            y=0.98,
            yanchor="top",
            font=dict(size=17, family="Segoe UI, system-ui, sans-serif"),
            pad=dict(b=12),
        ),
        height=height,
        font=dict(family="Segoe UI, system-ui, sans-serif", size=13),
        colorway=COLORWAY,
        paper_bgcolor="rgba(15,23,42,0.6)",
        plot_bgcolor="rgba(30,41,59,0.4)",
        margin=dict(l=68, r=36 + extra_right, t=top_margin, b=bottom_margin),
        hoverlabel=dict(font=dict(size=12)),
    )
    if legend_below and show_legend:
        fig.update_layout(
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.22,
                xanchor="center",
                x=0.5,
                font=dict(size=12),
                bgcolor="rgba(15,23,42,0.88)",
                bordercolor="rgba(148,163,184,0.3)",
                borderwidth=1,
                itemwidth=30,
            )
        )
    else:
        fig.update_layout(showlegend=False)

    fig.update_xaxes(
        automargin=True,
        tickfont=dict(size=12),
        title_font=dict(size=13),
        showgrid=True,
        gridcolor="rgba(148,163,184,0.12)",
    )
    fig.update_yaxes(
        automargin=True,
        tickfont=dict(size=12),
        title_font=dict(size=13),
        showgrid=True,
        gridcolor="rgba(148,163,184,0.12)",
    )


def empty_fig(title: str, message: str = "No data for current filters") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=14, color="#94a3b8"),
    )
    _fig_layout(fig, title, CHART_HEIGHT_SM, legend_below=False, show_legend=False)
    return fig


# US full name -> 2-letter (choropleth)
STATE_TO_ABBR = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
    "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}


# -----------------------------
# MONGODB + CLEANING
# -----------------------------
client = MongoClient("mongodb://127.0.0.1:27017/")
db = client["Sales"]
collection = db["Analysis"]

data = list(collection.find({}, {"_id": 0}))
df = pd.DataFrame(data)

if df.empty:
    df = pd.DataFrame(
        columns=[
            "Sales", "Profit", "Quantity", "Discount", "Order Date",
            "Category", "Sub-Category", "Region", "State", "Segment",
            "Ship Mode", "Ship Date",
        ]
    )

for col in ["Segment", "Ship Mode", "Ship Date", "Region", "State", "Category", "Sub-Category"]:
    if col not in df.columns:
        df[col] = pd.NA

df["Sales"] = pd.to_numeric(df["Sales"], errors="coerce")
df["Profit"] = pd.to_numeric(df["Profit"], errors="coerce")
df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
df["Discount"] = pd.to_numeric(df["Discount"], errors="coerce")
df["Order Date"] = pd.to_datetime(df["Order Date"], errors="coerce")
df["Ship Date"] = pd.to_datetime(df["Ship Date"], errors="coerce")

df = df.dropna(subset=["Sales", "Profit"])
df["Segment"] = df["Segment"].fillna("Unknown")
df["Ship Mode"] = df["Ship Mode"].fillna("Unknown")

if "Ship Date" in df.columns and df["Ship Date"].notna().any():
    df["lead_days"] = (df["Ship Date"] - df["Order Date"]).dt.days
else:
    df["lead_days"] = pd.NA

df["profit_margin"] = df.apply(
    lambda r: (r["Profit"] / r["Sales"]) if pd.notna(r["Sales"]) and r["Sales"] != 0 else pd.NA,
    axis=1,
)

categories = sorted(df["Category"].dropna().unique().tolist()) if len(df) else []
subcategories_map = {
    cat: sorted(df[df["Category"] == cat]["Sub-Category"].dropna().unique().tolist())
    for cat in categories
}
segments = sorted(df["Segment"].dropna().unique().tolist()) if len(df) else []

date_min = df["Order Date"].min() if len(df) else None
date_max = df["Order Date"].max() if len(df) else None
if date_min is not None and pd.isna(date_min):
    date_min = None
if date_max is not None and pd.isna(date_max):
    date_max = None
# DatePickerRange requires concrete bounds when empty DB
if date_min is None or date_max is None:
    today = pd.Timestamp.today().normalize()
    date_min = date_min or (today - pd.Timedelta(days=365))
    date_max = date_max or today


def apply_filters(
    frame: pd.DataFrame,
    category: str | None,
    subcategory: str | None,
    segment: str | None,
    start_date: str | None,
    end_date: str | None,
) -> pd.DataFrame:
    out = frame.copy()
    if start_date:
        out = out[out["Order Date"] >= pd.to_datetime(start_date)]
    if end_date:
        out = out[out["Order Date"] <= pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)]
    if category:
        out = out[out["Category"] == category]
    if subcategory:
        out = out[out["Sub-Category"] == subcategory]
    if segment:
        out = out[out["Segment"] == segment]
    return out


# -----------------------------
# CHART BUILDERS
# -----------------------------
def fig_category_bar(f: pd.DataFrame) -> go.Figure:
    if f.empty:
        return empty_fig("Sales by Category")
    agg = f.groupby("Category", as_index=False)["Sales"].sum()
    fig = px.bar(agg, x="Category", y="Sales", color="Category")
    _fig_layout(fig, "Sales by Category")
    return fig


def fig_monthly_line(f: pd.DataFrame) -> go.Figure:
    if f.empty or f["Order Date"].isna().all():
        return empty_fig("Monthly Sales Trend")
    g = f.groupby(f["Order Date"].dt.to_period("M"))["Sales"].sum().reset_index()
    g["Order Date"] = g["Order Date"].astype(str)
    fig = px.area(g, x="Order Date", y="Sales", color_discrete_sequence=[COLORWAY[0]])
    fig.update_traces(showlegend=False)
    _fig_layout(fig, "Monthly Sales Trend", legend_below=False, show_legend=False)
    return fig


def fig_region_pie(f: pd.DataFrame) -> go.Figure:
    if f.empty:
        return empty_fig("Sales by Region")
    fig = px.pie(f, names="Region", values="Sales", hole=0.38)
    fig.update_traces(
        textposition="inside",
        textinfo="percent",
        insidetextfont=dict(size=12),
    )
    _fig_layout(fig, "Sales by Region", extra_bottom=8)
    return fig


def fig_scatter_sales_profit(f: pd.DataFrame) -> go.Figure:
    if f.empty:
        return empty_fig("Sales vs Profit")
    fig = px.scatter(
        f, x="Sales", y="Profit", color="Category",
        hover_data=["Sub-Category", "Region"] if "Sub-Category" in f.columns else None,
        opacity=0.75,
    )
    _fig_layout(fig, "Sales vs Profit")
    return fig


def fig_geo_scatter(f: pd.DataFrame) -> go.Figure:
    if f.empty or f["State"].isna().all():
        return empty_fig("Sales by State (bubble map)")
    st = f.groupby("State", as_index=False).agg({"Sales": "sum", "Profit": "sum"})
    st["abbr"] = st["State"].map(STATE_TO_ABBR)
    st = st.dropna(subset=["abbr"])
    if st.empty:
        return empty_fig("Sales by State (bubble map)", "State names need US full names for mapping")
    fig = px.scatter_geo(
        st,
        locations="abbr",
        locationmode="USA-states",
        size="Sales",
        color="Profit",
        scope="usa",
        hover_name="State",
        size_max=55,
    )
    _fig_layout(fig, "Sales & profit by state (geo)", extra_bottom=12, extra_right=36)
    fig.update_layout(
        coloraxis_colorbar=dict(
            title=dict(text="Profit", font=dict(size=12)),
            thickness=14,
            len=0.55,
            tickfont=dict(size=11),
        )
    )
    return fig


def fig_calendar_heatmap(f: pd.DataFrame) -> go.Figure:
    if f.empty or f["Order Date"].isna().all():
        return empty_fig("Sales calendar heatmap (day × month)")
    t = f.copy()
    t["m"] = t["Order Date"].dt.month
    t["d"] = t["Order Date"].dt.day
    piv = t.pivot_table(index="d", columns="m", values="Sales", aggfunc="sum").fillna(0)
    if piv.size == 0:
        return empty_fig("Sales calendar heatmap (day × month)")
    fig = px.imshow(
        piv,
        labels=dict(x="Month", y="Day of month", color="Sales"),
        aspect="auto",
        color_continuous_scale="Blues",
    )
    _fig_layout(fig, "Sales density: day of month × month", legend_below=False, show_legend=False, extra_right=28)
    fig.update_layout(
        coloraxis_colorbar=dict(
            title=dict(text="Sales", font=dict(size=12)),
            thickness=14,
            len=0.75,
            tickfont=dict(size=11),
        )
    )
    return fig


def fig_lead_time(f: pd.DataFrame) -> go.Figure:
    if f.empty or f["lead_days"].isna().all():
        return empty_fig("Shipping lead time (days)")
    sub = f.dropna(subset=["lead_days"])
    if sub.empty:
        return empty_fig("Shipping lead time (days)", "Need Ship Date in data")
    fig = px.box(sub, x="Ship Mode", y="lead_days", color="Ship Mode", points="outliers")
    _fig_layout(fig, "Lead time (Ship Date − Order Date) by ship mode", extra_bottom=16)
    return fig


def fig_waterfall_overall(f: pd.DataFrame) -> go.Figure:
    if f.empty:
        return empty_fig("Revenue → costs → net profit")
    ts = float(f["Sales"].sum())
    tp = float(f["Profit"].sum())
    implied_costs = ts - tp
    fig = go.Figure(
        go.Waterfall(
            orientation="v",
            measure=["relative", "relative", "total"],
            x=["Revenue (sales)", "Implied costs (sales − profit)", "Net profit"],
            y=[ts, -implied_costs, tp],
            text=[f"{ts:,.0f}", f"{-implied_costs:,.0f}", f"{tp:,.0f}"],
            connector={"line": {"color": "rgb(148,163,184)"}},
            increasing={"marker": {"color": "#34d399"}},
            decreasing={"marker": {"color": "#f87171"}},
            totals={"marker": {"color": "#38bdf8"}},
        )
    )
    _fig_layout(fig, "Financial bridge: revenue, implied costs, net profit", legend_below=False, show_legend=False)
    return fig


def fig_choropleth_margin(f: pd.DataFrame) -> go.Figure:
    if f.empty or f["State"].isna().all():
        return empty_fig("Profit margin by state")
    st = f.groupby("State", as_index=False).agg({"Sales": "sum", "Profit": "sum"})
    st["abbr"] = st["State"].map(STATE_TO_ABBR)
    st = st.dropna(subset=["abbr"])
    st["margin"] = st.apply(
        lambda r: (r["Profit"] / r["Sales"]) if r["Sales"] else float("nan"),
        axis=1,
    )
    if st.empty:
        return empty_fig("Profit margin by state", "Could not map state names to abbreviations")
    fig = px.choropleth(
        st,
        locations="abbr",
        locationmode="USA-states",
        color="margin",
        scope="usa",
        color_continuous_scale="RdYlGn",
        hover_name="State",
        labels={"margin": "Profit margin"},
    )
    fig.update_traces(hovertemplate="<b>%{hovertext}</b><br>Margin: %{z:.1%}<extra></extra>")
    _fig_layout(fig, "Profit margin by state (choropleth)", legend_below=False, show_legend=False, extra_right=44)
    fig.update_layout(
        coloraxis_colorbar=dict(
            title=dict(text="Margin", font=dict(size=12)),
            tickformat=".0%",
            thickness=14,
            len=0.65,
            tickfont=dict(size=11),
        )
    )
    return fig


def fig_treemap(f: pd.DataFrame) -> go.Figure:
    if f.empty:
        return empty_fig("Hierarchy: region → state → category")
    t = f.dropna(subset=["Region", "State", "Category"])
    if t.empty:
        return empty_fig("Hierarchy: region → state → category", "Missing region/state/category")
    fig = px.treemap(
        t,
        path=[px.Constant("All"), "Region", "State", "Category"],
        values="Sales",
        color="Profit",
        color_continuous_scale="RdYlGn",
    )
    _fig_layout(fig, "Treemap: sales size, profit color", legend_below=False, show_legend=False, extra_right=40)
    fig.update_layout(
        coloraxis_colorbar=dict(
            title=dict(text="Profit", font=dict(size=12)),
            thickness=14,
            len=0.7,
            tickfont=dict(size=11),
        )
    )
    return fig


def fig_sunburst(f: pd.DataFrame) -> go.Figure:
    if f.empty:
        return empty_fig("Product hierarchy")
    t = f.dropna(subset=["Category", "Sub-Category"])
    if t.empty:
        return empty_fig("Product hierarchy")
    fig = px.sunburst(t, path=["Category", "Sub-Category"], values="Sales")
    _fig_layout(fig, "Sunburst: category → sub-category", legend_below=False, show_legend=False)
    return fig


def fig_pareto(f: pd.DataFrame) -> go.Figure:
    if f.empty:
        return empty_fig("Pareto: sub-category sales")
    sub = f.groupby("Sub-Category", as_index=False)["Sales"].sum().sort_values("Sales", ascending=False)
    if sub.empty:
        return empty_fig("Pareto: sub-category sales")
    sub["cum_pct"] = sub["Sales"].cumsum() / sub["Sales"].sum() * 100
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=sub["Sub-Category"], y=sub["Sales"], name="Sales", marker_color=COLORWAY[0]),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=sub["Sub-Category"],
            y=sub["cum_pct"],
            name="Cumulative %",
            mode="lines+markers",
            marker=dict(color=COLORWAY[1]),
        ),
        secondary_y=True,
    )
    fig.update_yaxes(title_text="Sales", secondary_y=False)
    fig.update_yaxes(title_text="Cumulative %", range=[0, 105], secondary_y=True)
    _fig_layout(fig, "Pareto: sub-category sales & cumulative %", extra_bottom=72)
    fig.update_layout(xaxis=dict(tickangle=-35, tickfont=dict(size=11)))
    return fig


def fig_parallel(f: pd.DataFrame) -> go.Figure:
    if f.empty:
        return empty_fig("Parallel coordinates (by sub-category)")
    agg = f.groupby("Sub-Category", as_index=False).agg(
        Sales=("Sales", "sum"),
        Profit=("Profit", "sum"),
        Quantity=("Quantity", "sum"),
        Discount=("Discount", "mean"),
    ).dropna()
    if len(agg) < 2:
        return empty_fig("Parallel coordinates (by sub-category)", "Need more sub-categories")
    fig = px.parallel_coordinates(
        agg,
        color="Profit",
        dimensions=["Sales", "Profit", "Quantity", "Discount"],
        color_continuous_scale="Blues",
    )
    _fig_layout(fig, "Parallel coordinates (aggregated by sub-category)", legend_below=False, show_legend=False, extra_right=52)
    fig.update_layout(
        coloraxis_colorbar=dict(
            title=dict(text="Profit", font=dict(size=12)),
            thickness=14,
            len=0.65,
            tickfont=dict(size=11),
        )
    )
    return fig


def fig_segment_stacked(f: pd.DataFrame) -> go.Figure:
    if f.empty or f["Order Date"].isna().all():
        return empty_fig("Monthly sales by segment")
    t = f.copy()
    t["ym"] = t["Order Date"].dt.to_period("M").astype(str)
    ms = t.groupby(["ym", "Segment"], as_index=False)["Sales"].sum()
    fig = px.bar(ms, x="ym", y="Sales", color="Segment", barmode="stack")
    _fig_layout(fig, "Stacked monthly sales by customer segment", extra_bottom=64)
    fig.update_layout(xaxis=dict(tickangle=-40, tickfont=dict(size=11)))
    return fig


def fig_segment_scatter(f: pd.DataFrame) -> go.Figure:
    if f.empty:
        return empty_fig("Sales vs profit (size = qty, color = segment)")
    fig = px.scatter(
        f,
        x="Sales",
        y="Profit",
        size="Quantity",
        color="Segment",
        size_max=28,
        opacity=0.65,
        hover_data=["Sub-Category", "Region"] if "Sub-Category" in f.columns else None,
    )
    _fig_layout(fig, "Sales vs profit — point size = quantity")
    return fig


def fig_density_discount_profit(f: pd.DataFrame) -> go.Figure:
    if f.empty:
        return empty_fig("Discount vs profit (density)")
    sub = f.dropna(subset=["Discount", "Profit"])
    if len(sub) < 5:
        return empty_fig("Discount vs profit (density)", "Not enough points")
    fig = px.density_heatmap(sub, x="Discount", y="Profit", nbinsx=24, nbinsy=24, color_continuous_scale="Viridis")
    _fig_layout(
        fig,
        "Discount vs profit density",
        height=CHART_HEIGHT + 56,
        legend_below=False,
        show_legend=False,
        extra_right=36,
    )
    fig.update_layout(
        coloraxis_colorbar=dict(
            title=dict(text="Count", font=dict(size=12)),
            thickness=14,
            len=0.72,
            tickfont=dict(size=11),
        )
    )
    return fig


def fig_waterfall_by_category(f: pd.DataFrame) -> go.Figure:
    if f.empty:
        return empty_fig("Profit bridge by category")
    cats = f["Category"].dropna().unique()
    if len(cats) == 0:
        return empty_fig("Profit bridge by category")
    n = len(cats)
    fig = make_subplots(
        rows=1,
        cols=n,
        subplot_titles=[str(c) for c in cats],
        horizontal_spacing=min(0.08, 0.02 + 0.03 * n),
    )
    for i, cat in enumerate(cats, start=1):
        cdf = f[f["Category"] == cat]
        ts = float(cdf["Sales"].sum())
        tp = float(cdf["Profit"].sum())
        ic = ts - tp
        fig.add_trace(
            go.Waterfall(
                orientation="v",
                measure=["relative", "relative", "total"],
                x=["Revenue", "Implied costs", "Net"],
                y=[ts, -ic, tp],
                text=[f"{ts:,.0f}", f"{-ic:,.0f}", f"{tp:,.0f}"],
                textfont=dict(size=11),
                connector={"line": {"color": "rgb(148,163,184)"}},
                showlegend=False,
            ),
            row=1,
            col=i,
        )
    _fig_layout(
        fig,
        "Profit bridge by category (small multiples)",
        height=460,
        legend_below=False,
        show_legend=False,
        extra_top=36,
    )
    fig.update_layout(height=480, margin=dict(t=120, b=72, l=56, r=40))
    fig.for_each_annotation(lambda a: a.update(font=dict(size=13, family="Segoe UI, system-ui, sans-serif")))
    return fig


def build_kpi_cards(f: pd.DataFrame) -> html.Div:
    if f.empty:
        return html.Div(
            className="kpi-row",
            children=[
                html.Div(className="kpi-card", children=[
                    html.Div("No rows", className="label"),
                    html.Div("Adjust filters or load MongoDB data", className="value"),
                ]),
            ],
        )
    total_sales = f["Sales"].sum()
    total_profit = f["Profit"].sum()
    total_qty = f["Quantity"].sum()
    avg_disc = f["Discount"].mean()
    margin = (total_profit / total_sales * 100) if total_sales else 0
    cards = [
        ("Total sales", f"${total_sales:,.2f}", False),
        ("Net profit", f"${total_profit:,.2f}", True),
        ("Units sold", f"{total_qty:,.0f}", False),
        ("Avg discount", f"{avg_disc:.2%}", False),
        ("Overall margin", f"{margin:.1f}%", True),
    ]
    return html.Div(
        className="kpi-row",
        children=[
            html.Div(
                className="kpi-card" + (" accent" if acc else ""),
                children=[
                    html.Div(lbl, className="label"),
                    html.Div(val, className="value"),
                ],
            )
            for lbl, val, acc in cards
        ],
    )


def build_anomaly_strip(f: pd.DataFrame) -> html.Div:
    if f.empty or f["Sub-Category"].isna().all():
        return html.Div(className="anomaly-strip", children=[])
    by_sub = f.groupby("Sub-Category", as_index=False).agg(Sales=("Sales", "sum"), Profit=("Profit", "sum"))
    by_sub["margin"] = by_sub.apply(
        lambda r: (r["Profit"] / r["Sales"]) if r["Sales"] else float("nan"),
        axis=1,
    )
    worst = by_sub.sort_values("margin").iloc[0] if len(by_sub) else None
    neg_states = []
    if f["State"].notna().any():
        st = f.groupby("State", as_index=False).agg(Profit=("Profit", "sum"))
        neg_states = st[st["Profit"] < 0]["State"].tolist()
    parts = []
    if worst is not None and pd.notna(worst["margin"]):
        parts.append(
            html.Div(
                className="anomaly-card warn",
                children=[
                    html.Strong("Lowest margin sub-category: "),
                    f"{worst['Sub-Category']} ({worst['margin']:.1%} margin on filtered data)",
                ],
            )
        )
    if neg_states:
        parts.append(
            html.Div(
                className="anomaly-card",
                children=[
                    html.Strong("States with negative profit: "),
                    ", ".join(neg_states[:12]) + ("…" if len(neg_states) > 12 else ""),
                ],
            )
        )
    if not parts:
        parts.append(
            html.Div(
                className="anomaly-card",
                children=[html.Strong("Insights: "), "No margin or geo anomalies detected on current slice."],
            )
        )
    return html.Div(className="anomaly-strip", children=parts)


# -----------------------------
# APP LAYOUT
# -----------------------------
app = dash.Dash(__name__)
app.title = "Sales Analysis"

app.layout = html.Div(
    className="dashboard-shell",
    children=[
        html.Div(
            className="dashboard-header",
            children=[
                html.H1("SALES INTELLIGENCE"),
                html.P("Superstore-style analytics — filter the story, explore every dimension."),
            ],
        ),
        html.Div(
            className="filter-bar",
            children=[
                html.Div(
                    className="filter-item",
                    children=[
                        html.Label("Order date range"),
                        dcc.DatePickerRange(
                            id="date_range",
                            min_date_allowed=date_min,
                            max_date_allowed=date_max,
                            start_date=date_min,
                            end_date=date_max,
                            display_format="YYYY-MM-DD",
                            minimum_nights=0,
                        ),
                    ],
                ),
                html.Div(
                    className="filter-item",
                    children=[
                        html.Label("Segment"),
                        dcc.Dropdown(
                            id="segment_filter",
                            options=[{"label": "All segments", "value": ""}] + [{"label": s, "value": s} for s in segments],
                            value="",
                            clearable=False,
                        ),
                    ],
                ),
                html.Div(
                    className="filter-item",
                    children=[
                        html.Label("Category"),
                        dcc.Dropdown(
                            id="category_filter",
                            options=[{"label": c, "value": c} for c in categories],
                            placeholder="All categories",
                            clearable=True,
                        ),
                    ],
                ),
                html.Div(
                    className="filter-item",
                    children=[
                        html.Label("Sub-category"),
                        dcc.Dropdown(
                            id="subcategory_filter",
                            placeholder="All sub-categories",
                            clearable=True,
                        ),
                    ],
                ),
            ],
        ),
        html.Div(id="kpi_cards"),
        html.Div(id="anomaly_strip"),
        dcc.Tabs(
            id="main_tabs",
            className="dash-tabs",
            children=[
                dcc.Tab(
                    label="Overview",
                    className="dash-tab",
                    selected_className="dash-tab--selected",
                    children=[
                        html.Div(
                            className="tab-content",
                            children=[
                                html.Div(
                                    className="chart-row",
                                    children=[
                                        dcc.Graph(id="g_cat_bar", config=GRAPH_CONFIG,
                                            style=GRAPH_STYLE,),
                                        dcc.Graph(id="g_month_line", config=GRAPH_CONFIG,
                                            style=GRAPH_STYLE,),
                                    ],
                                ),
                                html.Div(
                                    className="chart-row",
                                    children=[
                                        dcc.Graph(id="g_region_pie", config=GRAPH_CONFIG,
                                            style=GRAPH_STYLE,),
                                        dcc.Graph(id="g_scatter_basic", config=GRAPH_CONFIG,
                                            style=GRAPH_STYLE,),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
                dcc.Tab(
                    label="Time & operations",
                    className="dash-tab",
                    selected_className="dash-tab--selected",
                    children=[
                        html.Div(
                            className="tab-content",
                            children=[
                                html.Div(
                                    className="chart-row",
                                    children=[
                                        dcc.Graph(id="g_calendar", config=GRAPH_CONFIG,
                                            style=GRAPH_STYLE,),
                                        dcc.Graph(id="g_lead_box", config=GRAPH_CONFIG,
                                            style=GRAPH_STYLE,),
                                    ],
                                ),
                                html.Div(className="chart-full", children=[dcc.Graph(id="g_waterfall_main", config=GRAPH_CONFIG,
                                            style=GRAPH_STYLE,)]),
                            ],
                        ),
                    ],
                ),
                dcc.Tab(
                    label="Geography",
                    className="dash-tab",
                    selected_className="dash-tab--selected",
                    children=[
                        html.Div(
                            className="tab-content",
                            children=[
                                html.Div(
                                    className="chart-row",
                                    children=[
                                        dcc.Graph(id="g_choro_margin", config=GRAPH_CONFIG,
                                            style=GRAPH_STYLE,),
                                        dcc.Graph(id="g_geo_scatter", config=GRAPH_CONFIG,
                                            style=GRAPH_STYLE,),
                                    ],
                                ),
                                html.Div(className="chart-full", children=[dcc.Graph(id="g_treemap", config=GRAPH_CONFIG,
                                            style=GRAPH_STYLE,)]),
                            ],
                        ),
                    ],
                ),
                dcc.Tab(
                    label="Products",
                    className="dash-tab",
                    selected_className="dash-tab--selected",
                    children=[
                        html.Div(
                            className="tab-content",
                            children=[
                                html.Div(
                                    className="chart-row",
                                    children=[
                                        dcc.Graph(id="g_sunburst", config=GRAPH_CONFIG,
                                            style=GRAPH_STYLE,),
                                        dcc.Graph(id="g_pareto", config=GRAPH_CONFIG,
                                            style=GRAPH_STYLE,),
                                    ],
                                ),
                                html.Div(className="chart-full", children=[dcc.Graph(id="g_parallel", config=GRAPH_CONFIG,
                                            style=GRAPH_STYLE,)]),
                            ],
                        ),
                    ],
                ),
                dcc.Tab(
                    label="Customers & finance",
                    className="dash-tab",
                    selected_className="dash-tab--selected",
                    children=[
                        html.Div(
                            className="tab-content",
                            children=[
                                html.Div(
                                    className="chart-row",
                                    children=[
                                        dcc.Graph(id="g_segment_stack", config=GRAPH_CONFIG,
                                            style=GRAPH_STYLE,),
                                        dcc.Graph(id="g_segment_scatter", config=GRAPH_CONFIG,
                                            style=GRAPH_STYLE,),
                                    ],
                                ),
                                html.Div(
                                    className="chart-full",
                                    children=[dcc.Graph(id="g_density", config=GRAPH_CONFIG,
                                            style=GRAPH_STYLE,)],
                                ),
                                html.Div(className="chart-full", children=[dcc.Graph(id="g_waterfall_cats", config=GRAPH_CONFIG,
                                            style=GRAPH_STYLE,)]),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    ],
)


# -----------------------------
# CALLBACKS
# -----------------------------
@app.callback(
    Output("subcategory_filter", "options"),
    Input("category_filter", "value"),
)
def update_subcategory_options(selected_category):
    if not selected_category:
        return []
    subs = subcategories_map.get(selected_category, [])
    return [{"label": s, "value": s} for s in subs]


@app.callback(
    [
        Output("kpi_cards", "children"),
        Output("anomaly_strip", "children"),
        Output("g_cat_bar", "figure"),
        Output("g_month_line", "figure"),
        Output("g_region_pie", "figure"),
        Output("g_scatter_basic", "figure"),
        Output("g_calendar", "figure"),
        Output("g_lead_box", "figure"),
        Output("g_waterfall_main", "figure"),
        Output("g_choro_margin", "figure"),
        Output("g_geo_scatter", "figure"),
        Output("g_treemap", "figure"),
        Output("g_sunburst", "figure"),
        Output("g_pareto", "figure"),
        Output("g_parallel", "figure"),
        Output("g_segment_stack", "figure"),
        Output("g_segment_scatter", "figure"),
        Output("g_density", "figure"),
        Output("g_waterfall_cats", "figure"),
    ],
    [
        Input("date_range", "start_date"),
        Input("date_range", "end_date"),
        Input("segment_filter", "value"),
        Input("category_filter", "value"),
        Input("subcategory_filter", "value"),
    ],
)
def update_all(start_date, end_date, segment, category, subcategory):
    seg = segment or None
    cat = category or None
    sub = subcategory or None
    filtered = apply_filters(df, cat, sub, seg, start_date, end_date)

    return (
        build_kpi_cards(filtered),
        build_anomaly_strip(filtered),
        fig_category_bar(filtered),
        fig_monthly_line(filtered),
        fig_region_pie(filtered),
        fig_scatter_sales_profit(filtered),
        fig_calendar_heatmap(filtered),
        fig_lead_time(filtered),
        fig_waterfall_overall(filtered),
        fig_choropleth_margin(filtered),
        fig_geo_scatter(filtered),
        fig_treemap(filtered),
        fig_sunburst(filtered),
        fig_pareto(filtered),
        fig_parallel(filtered),
        fig_segment_stacked(filtered),
        fig_segment_scatter(filtered),
        fig_density_discount_profit(filtered),
        fig_waterfall_by_category(filtered),
    )


if __name__ == "__main__":
    app.run(debug=True)
