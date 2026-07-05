"""Pandas-only dataset insight helpers for the map chatbox."""

from __future__ import annotations

import pandas as pd

from labelmap.data_filter import filter_status_text
from labelmap.ui_copy import UI_COPY, display_value_column

try:
    import altair as alt
except ImportError:  # pragma: no cover - altair ships with Streamlit
    alt = None


def _format_number(value) -> str:
    if pd.isna(value):
        return "—"
    if isinstance(value, float):
        if value == int(value):
            return f"{int(value):,}"
        return f"{value:,.2f}"
    return str(value)


def one_line_narrative(
    df: pd.DataFrame,
    name_col: str,
    value_cols: list[str],
    dataset_name: str,
) -> str:
    """Return a one-line overview of the active dataset."""
    location_count = len(df)
    if not value_cols:
        return f"{location_count:,} locations · {dataset_name}"

    primary = value_cols[0]
    metric_label = display_value_column(primary)
    numeric = df[primary].dropna()
    if numeric.empty:
        return (
            f"{location_count:,} locations · {len(value_cols)} metric(s) · {dataset_name}"
        )

    top_idx = numeric.idxmax()
    top_row = df.loc[top_idx]
    top_name = top_row[name_col]
    top_value = _format_number(top_row[primary])
    return (
        f"{location_count:,} locations · {len(value_cols)} metric(s) · "
        f"highest {metric_label}: {top_name} ({top_value})"
    )


def build_greeting(
    filtered_df: pd.DataFrame,
    full_df: pd.DataFrame,
    name_col: str,
    value_cols: list[str],
    dataset_name: str,
    *,
    regions: list[str] | None = None,
    countries: list[str] | None = None,
    locations: list[str] | None = None,
    search: str | None = None,
) -> str:
    """Build the assistant greeting for the insight chat."""
    narrative = one_line_narrative(filtered_df, name_col, value_cols, dataset_name)
    status = filter_status_text(
        len(filtered_df),
        len(full_df),
        regions=regions,
        countries=countries,
        locations=locations,
        search=search,
    )
    lines = [UI_COPY.insight_greeting, narrative]
    if status:
        lines.append(status)
    return "\n\n".join(lines)


def action_intro_text(
    action: str,
    metric: str | None = None,
    *,
    metrics: list[str] | None = None,
) -> str:
    """Return a short assistant intro for a selected action."""
    metric_label = display_value_column(metric) if metric else None
    metric_labels = [display_value_column(column) for column in (metrics or [])]
    intros = {
        "summary": "Here is a statistical summary of the current view.",
        "top10": (
            f"Here are the top 10 locations by {metric_label}."
            if metric_label
            else "Here are the top 10 locations."
        ),
        "bottom10": (
            f"Here are the bottom 10 locations by {metric_label}."
            if metric_label
            else "Here are the bottom 10 locations."
        ),
        "bar_chart": (
            f"Bar chart of the top 10 locations by {metric_label}."
            if metric_label
            else "Bar chart of the top 10 locations."
        ),
        "bar_chart_compare": (
            (
                f"Grouped bars ({metric_labels[0]} and {metric_labels[1]}) with "
                f"% change line ({metric_labels[1]} vs {metric_labels[0]}) "
                "for the top 10 locations."
            )
            if len(metric_labels) >= 2
            else (
                "Comparison chart of the top 10 locations by "
                + ", ".join(metric_labels)
                + "."
                if metric_labels
                else "Comparison chart of the top 10 locations."
            )
        ),
        "column_chart": (
            f"Column chart of the top 10 locations by {metric_label}."
            if metric_label
            else "Column chart of the top 10 locations."
        ),
        "full_table": "Here is the full data table for the current view.",
        "map": "Here's your current map.",
        "missing": "Here are the missing-value counts for each column.",
        "download": "Your filtered dataset is ready to download.",
    }
    return intros.get(action, "Here is what you asked for.")


def summary_table(df: pd.DataFrame, value_cols: list[str]) -> pd.DataFrame:
    """Descriptive stats for value columns, including missing counts."""
    if not value_cols:
        return pd.DataFrame()

    stats = df[value_cols].describe().T
    stats["missing"] = df[value_cols].isna().sum()
    return stats


def ranked_table(
    df: pd.DataFrame,
    name_col: str,
    value_col: str,
    *,
    n: int = 10,
    ascending: bool = False,
) -> pd.DataFrame:
    """Return top or bottom rows for a value column."""
    subset = df[[name_col, value_col]].dropna(subset=[value_col])
    ordered = subset.sort_values(value_col, ascending=ascending)
    return ordered.head(n).reset_index(drop=True)


def chart_data(
    df: pd.DataFrame,
    name_col: str,
    value_col: str,
    *,
    n: int = 10,
) -> pd.DataFrame:
    """Return top-N rows indexed by location name for vertical bar charts."""
    ranked = ranked_table(df, name_col, value_col, n=n, ascending=False)
    return ranked.set_index(name_col)[[value_col]]


def comparison_percent_change(baseline, value) -> float | None:
    """Return percent change from baseline to value, or None when undefined."""
    if pd.isna(baseline) or pd.isna(value):
        return None
    baseline_f = float(baseline)
    value_f = float(value)
    if baseline_f == 0:
        return None
    return (value_f - baseline_f) / baseline_f * 100.0


def comparison_chart_data(
    df: pd.DataFrame,
    name_col: str,
    value_cols: list[str],
    *,
    n: int = 10,
) -> pd.DataFrame:
    """Return top-N locations ranked by the first metric with multiple metric columns."""
    if not value_cols:
        return pd.DataFrame()

    primary = value_cols[0]
    ranked = ranked_table(df, name_col, primary, n=n, ascending=False)
    top_locations = ranked[name_col].tolist()
    chart_df = df.set_index(name_col).loc[top_locations, value_cols].copy()
    chart_df.columns = [display_value_column(column) for column in value_cols]
    return chart_df


def comparison_combo_chart(
    df: pd.DataFrame,
    name_col: str,
    value_cols: list[str],
    *,
    n: int = 10,
):
    """Build a dual-axis chart: grouped bars (left) and % change points with labels."""
    if alt is None or len(value_cols) < 2:
        return None

    metric_a, metric_b = value_cols[0], value_cols[1]
    label_a = display_value_column(metric_a)
    label_b = display_value_column(metric_b)

    ranked = ranked_table(df, name_col, metric_a, n=n, ascending=False)
    locations = ranked[name_col].astype(str).tolist()

    bar_rows: list[dict[str, object]] = []
    line_rows: list[dict[str, object]] = []
    for loc in locations:
        matches = df[df[name_col].astype(str) == loc]
        if matches.empty:
            continue
        row = matches.iloc[0]
        v_a = row[metric_a]
        v_b = row[metric_b]
        bar_rows.append({"location": loc, "metric": label_a, "value": v_a})
        bar_rows.append({"location": loc, "metric": label_b, "value": v_b})
        pct = comparison_percent_change(v_a, v_b)
        line_rows.append(
            {
                "location": loc,
                "pct_change": pct,
                "pct_label": f"{pct:+.1f}%" if pct is not None else "",
            }
        )

    if not bar_rows:
        return None

    bar_data = pd.DataFrame(bar_rows)
    line_data = pd.DataFrame(line_rows)

    location_axis = alt.X(
        "location:N",
        sort=locations,
        title=None,
        axis=alt.Axis(labelAngle=-45),
    )

    bars = (
        alt.Chart(bar_data)
        .mark_bar(opacity=0.92)
        .encode(
            x=location_axis,
            y=alt.Y("value:Q", title="Value"),
            xOffset="metric:N",
            color=alt.Color(
                "metric:N",
                title=None,
                scale=alt.Scale(range=["#4F8DF7", "#00DAC3"]),
            ),
        )
    )

    pct_y = alt.Y("pct_change:Q", title=None, axis=None)
    points = (
        alt.Chart(line_data)
        .mark_point(color="#FF9230", size=70)
        .encode(x=location_axis, y=pct_y)
    )
    pct_labels = (
        alt.Chart(line_data)
        .mark_text(align="center", baseline="bottom", dy=-8, color="#FF9230", fontSize=11)
        .encode(x=location_axis, y=pct_y, text="pct_label:N")
    )

    return (
        alt.layer(bars, points, pct_labels)
        .resolve_scale(y="independent")
        .properties(height=320)
    )


def column_chart_data(
    df: pd.DataFrame,
    name_col: str,
    value_col: str,
    *,
    n: int = 10,
) -> pd.DataFrame:
    """Return top-N rows indexed by metric for horizontal-style column charts."""
    ranked = ranked_table(df, name_col, value_col, n=n, ascending=False)
    chart_df = ranked.set_index(value_col)[[name_col]].sort_index()
    chart_df.columns = [display_value_column(value_col)]
    return chart_df


def full_table(df: pd.DataFrame) -> pd.DataFrame:
    """Return the dataframe without internal index noise."""
    return df.reset_index(drop=True)


def missing_table(df: pd.DataFrame) -> pd.DataFrame:
    """Return missing-value counts for every column."""
    counts = df.isna().sum()
    return counts.rename("missing").to_frame()
