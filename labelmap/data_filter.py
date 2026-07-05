"""Geographic and text filters shared by the map and insight chat."""

from __future__ import annotations

import pandas as pd

from labelmap.data_io import has_geographic_metadata


def parse_loc_country(location_name: str) -> str:
    """Extract a country label from a location string such as 'United States, SPX500'."""
    if not isinstance(location_name, str):
        return ""
    parts = [part.strip() for part in location_name.split(",")]
    if len(parts) >= 2 and parts[0]:
        return parts[0]
    if " • " in location_name:
        return location_name.split(" • ", 1)[0].strip()
    return location_name.strip()


def location_filter_key(location_name: str) -> str:
    """Return a stable location key for filters (ignores live timestamps)."""
    if not isinstance(location_name, str):
        return ""
    if " • " in location_name:
        return location_name.split(" • ", 1)[0].strip()
    parts = [part.strip() for part in location_name.split(",")]
    if len(parts) >= 2 and parts[-1]:
        return parts[-1]
    return location_name.strip()


def _location_names(df: pd.DataFrame, name_col: str) -> pd.Series:
    return df[name_col].astype(str)


def _country_match_mask(df: pd.DataFrame, name_col: str, countries: list[str]) -> pd.Series:
    if not countries:
        return pd.Series(True, index=df.index)
    normalized = {country.casefold() for country in countries}
    names = _location_names(df, name_col)
    parsed = names.map(parse_loc_country).str.casefold()
    return names.str.casefold().isin(normalized) | parsed.isin(normalized)


def apply_data_filters(
    df: pd.DataFrame,
    *,
    regions: list[str] | None = None,
    countries: list[str] | None = None,
    locations: list[str] | None = None,
    search: str | None = None,
    name_col: str,
) -> pd.DataFrame:
    """Return a filtered copy of the dataframe using AND semantics."""
    if df is None or df.empty:
        return df

    filtered = df
    active_regions = [region for region in (regions or []) if region]
    active_countries = [country for country in (countries or []) if country]
    active_locations = [location for location in (locations or []) if location]
    active_search = (search or "").strip()

    if active_regions and has_geographic_metadata(filtered):
        filtered = filtered[filtered["Region"].isin(active_regions)]

    if active_countries:
        filtered = filtered[_country_match_mask(filtered, name_col, active_countries)]

    if active_locations:
        names = _location_names(filtered, name_col)
        filter_keys = {location_filter_key(location) for location in active_locations}
        name_keys = names.map(location_filter_key)
        filtered = filtered[name_keys.isin(filter_keys)]

    if active_search:
        names = _location_names(filtered, name_col)
        parsed = names.map(parse_loc_country)
        mask = names.str.contains(active_search, case=False, na=False) | parsed.str.contains(
            active_search, case=False, na=False
        )
        filtered = filtered[mask]

    return filtered.reset_index(drop=True)


def available_regions(df: pd.DataFrame) -> list[str]:
    """Return sorted unique World Bank regions present in the dataframe."""
    if not has_geographic_metadata(df):
        return []
    regions = df["Region"].dropna().astype(str).unique().tolist()
    return sorted(regions)


def available_locations(df: pd.DataFrame, name_col: str) -> list[str]:
    """Return sorted unique location names from the place-name column."""
    if df is None or df.empty or name_col not in df.columns:
        return []
    return sorted(df[name_col].dropna().astype(str).unique().tolist())


def filter_is_active(
    *,
    regions: list[str] | None = None,
    countries: list[str] | None = None,
    locations: list[str] | None = None,
    search: str | None = None,
) -> bool:
    return (
        bool([region for region in (regions or []) if region])
        or bool([country for country in (countries or []) if country])
        or bool([location for location in (locations or []) if location])
        or bool((search or "").strip())
    )


def filter_status_text(
    filtered_count: int,
    total_count: int,
    *,
    regions: list[str] | None = None,
    countries: list[str] | None = None,
    locations: list[str] | None = None,
    search: str | None = None,
) -> str:
    """Build a compact filter summary for the chat panel."""
    if not filter_is_active(
        regions=regions, countries=countries, locations=locations, search=search
    ):
        return ""

    parts = [f"Showing {filtered_count:,} of {total_count:,} locations"]
    active_regions = [region for region in (regions or []) if region]
    active_countries = [country for country in (countries or []) if country]
    active_locations = [location for location in (locations or []) if location]
    active_search = (search or "").strip()

    detail_parts = []
    if active_regions:
        detail_parts.append(", ".join(active_regions))
    if active_countries:
        detail_parts.append(", ".join(active_countries))
    if active_locations:
        detail_parts.append(", ".join(active_locations))
    if active_search:
        detail_parts.append(f'"{active_search}"')

    if detail_parts:
        parts.append(" · ".join(detail_parts))
    return " · ".join(parts)


def clear_filter_state(session_state) -> None:
    """Remove all insight filter keys from Streamlit session state."""
    session_state.pop("data_insight_filter_regions", None)
    session_state.pop("data_insight_filter_countries", None)
    session_state.pop("data_insight_filter_locations", None)
    session_state.pop("data_insight_filter_pending_locations", None)
    session_state.pop("data_insight_filter_location_options", None)
    session_state.pop("data_insight_search", None)


def get_filter_state(session_state) -> dict[str, object]:
    """Read the current insight filter values from session state."""
    return {
        "regions": list(session_state.get("data_insight_filter_regions") or []),
        "countries": list(session_state.get("data_insight_filter_countries") or []),
        "locations": list(session_state.get("data_insight_filter_locations") or []),
        "search": str(session_state.get("data_insight_search") or ""),
    }
