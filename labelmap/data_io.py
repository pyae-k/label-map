"""CSV loading and column-mapping helpers."""

import json
import os
import time
from datetime import datetime, timezone
from functools import lru_cache
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import pandas as pd

from labelmap.paths import repo_root, template_file_path
from labelmap.world_bank_baselines import WORLD_BANK_BASELINE_BY_LABEL

YAHOO_MARKET_SYMBOLS = {
    "SPX500": "^GSPC",
    "UK100": "^FTSE",
    "GRA40": "^FCHI",
    "JPN225": "^N225",
    "HKG50": "^HSI",
    "AUS200": "^AXJO",
    "Canada60": "^GSPTSE",
}

MARKET_TIMEZONES = {
    "SPX500": "America/New_York",
    "Canada60": "America/Toronto",
    "UK100": "Europe/London",
    "GRA40": "Europe/Paris",
    "JPN225": "Asia/Tokyo",
    "HKG50": "Asia/Hong_Kong",
    "AUS200": "Australia/Sydney",
}

LIVE_VALUE_COLUMNS = ("World Index 1d %", "World Index 7d %", "World Index 30d %")
COMPARISON_VALUE_COLUMNS = ("1d Ago", "7d Ago", "30d Ago", "Last value")
YAHOO_API_HEADERS = {"User-Agent": "Mozilla/5.0 (LabelMap; +https://github.com/pyaek/label-map)"}
WORLD_BANK_API_HEADERS = {"User-Agent": "Mozilla/5.0 (LabelMap; +https://github.com/pyaek/label-map)"}

# World Bank country metadata omits coordinates for a few territories.
WORLD_BANK_COORDINATE_FALLBACKS = {
    "CHI": (49.4556, -2.5361),  # Channel Islands — St Peter Port
    "CUW": (12.1080, -68.9335),  # Curacao — Willemstad
    "GIB": (36.1408, -5.3536),  # Gibraltar
    "MAF": (18.0708, -63.0847),  # St. Martin (French part) — Marigot
    "PSE": (31.9038, 35.2034),  # West Bank and Gaza — Ramallah
    "SXM": (18.0237, -63.0458),  # Sint Maarten (Dutch part) — Philipsburg
}


def _load_world_index_sample_dataframe():
    """Load the static world-index sample dataframe.

    Priority:
    1. bundled data/world_index.csv
    2. legacy repo root top20_gdp_countries_2023.csv
    """
    root = repo_root()
    candidates = [
        root / "data" / "world_index.csv",
        root / "top20_gdp_countries_2023.csv",
    ]
    for csv_path in candidates:
        if not csv_path.is_file():
            continue
        try:
            return pd.read_csv(csv_path)
        except Exception:
            continue
    return None


def _fetch_world_bank_json(url, max_attempts=3):
    last_error = None
    for attempt in range(max_attempts):
        try:
            request = Request(url, headers=WORLD_BANK_API_HEADERS)
            with urlopen(request, timeout=30) as response:  # nosec B310
                return json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < max_attempts - 1:
                time.sleep(1.5 * (attempt + 1))
    raise last_error


def _paginated_world_bank_rows(url_template, per_page=400):
    rows = []
    page = 1
    while True:
        separator = "&" if "?" in url_template else "?"
        url = f"{url_template}{separator}format=json&per_page={per_page}&page={page}"
        payload = None
        for attempt in range(3):
            payload = _fetch_world_bank_json(url)
            if isinstance(payload, list) and len(payload) >= 2:
                break
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
        if not isinstance(payload, list) or len(payload) < 2:
            raise ValueError("Unexpected World Bank API response shape")
        meta, page_rows = payload
        if not isinstance(meta, dict) or not isinstance(page_rows, list):
            raise ValueError("Unexpected World Bank API response shape")
        rows.extend(page_rows)
        if page >= meta["pages"]:
            break
        page += 1
    return rows


def _world_bank_coordinate_pair(country):
    latitude = country.get("latitude")
    longitude = country.get("longitude")
    if latitude not in (None, "") and longitude not in (None, ""):
        return float(latitude), float(longitude)
    return WORLD_BANK_COORDINATE_FALLBACKS.get(country["id"])


@lru_cache(maxsize=1)
def _fetch_world_bank_countries():
    return [
        country
        for country in _paginated_world_bank_rows("https://api.worldbank.org/v2/country")
        if country.get("region", {}).get("value") != "Aggregates"
    ]


@lru_cache(maxsize=None)
def _fetch_indicator_values(indicator, year):
    indicator_rows = _paginated_world_bank_rows(
        "https://api.worldbank.org/v2/country/all/indicator/"
        f"{indicator}?date={year}",
        per_page=2000,
    )
    return {
        row["countryiso3code"]: row["value"]
        for row in indicator_rows
        if row.get("countryiso3code") and row.get("value") is not None
    }


def _format_baseline_value(raw_value, value_kind):
    numeric_value = float(raw_value)
    if value_kind == "int":
        return int(round(numeric_value))
    return numeric_value


def _baseline_values_by_iso3(baseline):
    if baseline.is_derived:
        numerator_values = _fetch_indicator_values(baseline.derived_numerator, baseline.year)
        denominator_values = _fetch_indicator_values(
            baseline.derived_denominator, baseline.year
        )
        values_by_iso3 = {}
        for iso3, numerator in numerator_values.items():
            denominator = denominator_values.get(iso3)
            if denominator in (None, 0):
                continue
            values_by_iso3[iso3] = numerator / denominator
        return values_by_iso3

    return _fetch_indicator_values(baseline.indicator, baseline.year)


def _world_bank_country_metadata_by_name():
    """Map World Bank country display names to ISO3 and region labels."""
    metadata = {}
    for country in _fetch_world_bank_countries():
        region = country.get("region", {}).get("value")
        if not region or region == "Aggregates":
            continue
        metadata[country["name"]] = {
            "ISO3": country["id"],
            "Region": region,
        }
    return metadata


def _enrich_world_bank_metadata(df):
    """Add ISO3 and Region columns when loading bundled CSV fallbacks."""
    if df is None or df.empty or "Loc" not in df.columns:
        return df
    if "Region" in df.columns and "ISO3" in df.columns:
        return df
    metadata = _world_bank_country_metadata_by_name()
    enriched = df.copy()
    enriched["ISO3"] = enriched["Loc"].map(lambda name: metadata.get(name, {}).get("ISO3"))
    enriched["Region"] = enriched["Loc"].map(lambda name: metadata.get(name, {}).get("Region"))
    return enriched


def has_geographic_metadata(df):
    """Return True when the dataframe includes World Bank region metadata."""
    return df is not None and not df.empty and "Region" in df.columns


def build_world_bank_dataframe(baseline):
    """Build baseline rows from World Bank country metadata and indicator values."""
    values_by_iso3 = _baseline_values_by_iso3(baseline)
    records = []
    for country in _fetch_world_bank_countries():
        raw_value = values_by_iso3.get(country["id"])
        coordinates = _world_bank_coordinate_pair(country)
        if raw_value is None or coordinates is None:
            continue
        lat, lon = coordinates
        region = country.get("region", {}).get("value")
        records.append(
            {
                "Loc": country["name"],
                "Lat": lat,
                "Lon": lon,
                "ISO3": country["id"],
                "Region": region,
                baseline.value_column: _format_baseline_value(raw_value, baseline.value_kind),
            }
        )

    if not records:
        return None
    dataframe = pd.DataFrame(records)
    return dataframe.sort_values(baseline.value_column, ascending=False, ignore_index=True)


def _load_world_bank_csv(baseline):
    root = repo_root()
    candidates = [
        root / "data" / "world_bank" / f"{baseline.csv_slug}.csv",
    ]
    if baseline.label == "Population":
        candidates.extend(
            [
                root / "population_by_countries_or_locations.csv",
                root / "data" / "population_by_countries_or_locations.csv",
            ]
        )
    for path in candidates:
        if path.is_file():
            return pd.read_csv(path)
    return None


def load_world_bank_baseline(label):
    """Load a World Bank baseline from the API, with bundled CSV fallback."""
    baseline = WORLD_BANK_BASELINE_BY_LABEL.get(label)
    if baseline is None:
        return None
    try:
        dataframe = build_world_bank_dataframe(baseline)
        if dataframe is not None and not dataframe.empty:
            return dataframe
    except (OSError, ValueError, json.JSONDecodeError, KeyError, TypeError):
        pass
    csv_dataframe = _load_world_bank_csv(baseline)
    if csv_dataframe is None:
        return None
    return _enrich_world_bank_metadata(csv_dataframe)


def _extract_market_code(location_name):
    if not isinstance(location_name, str):
        return None
    parts = [part.strip() for part in location_name.split(",")]
    if len(parts) < 2:
        return None
    return parts[-1] or None


def _resolve_yahoo_symbol(market_code):
    if not market_code:
        return None
    return YAHOO_MARKET_SYMBOLS.get(market_code, market_code)


def _fetch_yahoo_points(symbol):
    url = (
        "https://query2.finance.yahoo.com/v8/finance/chart/"
        f"{quote(symbol)}?range=1mo&interval=1d&includePrePost=false&events=div%2Csplit"
    )
    request = Request(url, headers=YAHOO_API_HEADERS)
    with urlopen(request, timeout=8) as response:  # nosec B310
        payload = json.loads(response.read().decode("utf-8"))
    result = payload.get("chart", {}).get("result")
    if not result:
        return []
    first = result[0]
    timestamps = first.get("timestamp", [])
    quote_data = first.get("indicators", {}).get("quote", [])
    if not quote_data:
        return []
    closes = quote_data[0].get("close", [])
    points = []
    for timestamp, close in zip(timestamps, closes):
        if close is None:
            continue
        points.append((int(timestamp), float(close)))
    return points


def _fetch_yahoo_spark_points(symbols):
    if not symbols:
        return {}
    encoded_symbols = ",".join(quote(symbol) for symbol in symbols)
    url = (
        "https://query2.finance.yahoo.com/v7/finance/spark"
        f"?symbols={encoded_symbols}&range=1mo&interval=1d"
    )
    request = Request(url, headers=YAHOO_API_HEADERS)
    with urlopen(request, timeout=10) as response:  # nosec B310
        payload = json.loads(response.read().decode("utf-8"))

    result = payload.get("spark", {}).get("result", [])
    points_by_symbol = {}
    for entry in result:
        symbol = entry.get("symbol")
        responses = entry.get("response", [])
        if not symbol or not responses:
            continue
        first = responses[0]
        timestamps = first.get("timestamp", [])
        quote_data = first.get("indicators", {}).get("quote", [])
        if not quote_data:
            continue
        closes = quote_data[0].get("close", [])
        points = []
        for timestamp, close in zip(timestamps, closes):
            if close is None:
                continue
            points.append((int(timestamp), float(close)))
        if points:
            points_by_symbol[symbol] = points
    return points_by_symbol


def _format_market_timestamp(unix_ts, market_code):
    tz_name = MARKET_TIMEZONES.get(market_code, "UTC")
    dt = datetime.fromtimestamp(unix_ts, tz=timezone.utc).astimezone(ZoneInfo(tz_name))
    return dt.strftime("%b %d %H:%M")


def _value_at_or_before(points, target_ts):
    if not points:
        return None
    for timestamp, value in reversed(points):
        if timestamp <= target_ts:
            return value
    return points[0][1]


def _pct_change(current_value, previous_value):
    if previous_value in (None, 0):
        return None
    return ((current_value - previous_value) / abs(previous_value)) * 100


def _market_values_from_points(points, market_code=None):
    if not points:
        return None
    ordered = sorted(points, key=lambda item: item[0])
    last_ts, last_value = ordered[-1]
    one_day_reference = ordered[-2][1] if len(ordered) > 1 else None
    seven_day_reference = _value_at_or_before(ordered, last_ts - (7 * 24 * 60 * 60))
    thirty_day_reference = _value_at_or_before(ordered, last_ts - (30 * 24 * 60 * 60))
    timestamp_text = _format_market_timestamp(last_ts, market_code) if market_code else (
        datetime.fromtimestamp(last_ts, tz=timezone.utc).strftime("%b %d %H:%M")
    )
    return {
        "Last value": last_value,
        "1d Ago": one_day_reference,
        "7d Ago": seven_day_reference,
        "30d Ago": thirty_day_reference,
        "World Index 1d %": _pct_change(last_value, one_day_reference),
        "World Index 7d %": _pct_change(last_value, seven_day_reference),
        "World Index 30d %": _pct_change(last_value, thirty_day_reference),
        "__timestamp_text": timestamp_text,
    }


def _build_live_market_values(market_codes):
    resolved_symbols = {}
    for market_code in market_codes:
        symbol = _resolve_yahoo_symbol(market_code)
        if symbol:
            resolved_symbols[market_code] = symbol

    spark_points = {}
    try:
        spark_points = _fetch_yahoo_spark_points(sorted(set(resolved_symbols.values())))
    except (OSError, ValueError, json.JSONDecodeError):
        spark_points = {}

    live_values = {}
    for market_code, symbol in resolved_symbols.items():
        points = spark_points.get(symbol, [])
        if not points:
            try:
                points = _fetch_yahoo_points(symbol)
            except (OSError, ValueError, json.JSONDecodeError):
                points = []
        values = _market_values_from_points(points, market_code=market_code)
        if values is not None:
            live_values[market_code] = values
    return live_values


def _merge_live_market_values(df):
    if "Loc" not in df.columns:
        return df
    market_codes = {
        code
        for code in (_extract_market_code(location_name) for location_name in df["Loc"].tolist())
        if code
    }
    if not market_codes:
        return df
    live_values = _build_live_market_values(market_codes)

    enriched = df.copy()
    for column in (*COMPARISON_VALUE_COLUMNS, *LIVE_VALUE_COLUMNS):
        if column not in enriched.columns:
            enriched[column] = pd.NA
    for index, location_name in enriched["Loc"].items():
        market_code = _extract_market_code(location_name)
        if not market_code:
            continue
        tz_name = MARKET_TIMEZONES.get(market_code, "UTC")
        timestamp_text = datetime.now(tz=ZoneInfo(tz_name)).strftime("%b %d %H:%M")
        market_live_values = live_values.get(market_code)
        if market_live_values is None:
            enriched.at[index, "Loc"] = f"{market_code} • {timestamp_text}"
            continue
        for column, value in market_live_values.items():
            if column.startswith("__"):
                continue
            if value is not None:
                enriched.at[index, column] = value
        enriched.at[index, "Loc"] = f"{market_code} • {timestamp_text}"

    for column in (*COMPARISON_VALUE_COLUMNS, *LIVE_VALUE_COLUMNS):
        enriched[column] = pd.to_numeric(enriched[column], errors="coerce")
    return enriched


def load_sample_dataframe(sample_kind="world_index"):
    """Load default sample data for built-in baseline modes."""
    if sample_kind in WORLD_BANK_BASELINE_BY_LABEL:
        return load_world_bank_baseline(sample_kind)
    if sample_kind == "population":
        return load_world_bank_baseline("Population")
    bundled = _load_world_index_sample_dataframe()
    if bundled is None:
        return None
    return _merge_live_market_values(bundled)


def user_uploaded_spreadsheet(uploaded_file):
    if uploaded_file is None:
        return False
    size = getattr(uploaded_file, "size", None)
    if size is not None:
        return size > 0
    return True


def resolve_spreadsheet_source(uploaded_file):
    """Use uploaded CSV when present; otherwise load bundled map.xlsx as the example."""
    if user_uploaded_spreadsheet(uploaded_file):
        return uploaded_file, uploaded_file.name, False
    sample_path = template_file_path()
    if sample_path:
        return sample_path, os.path.basename(sample_path), True
    return None, None, False


def read_spreadsheet(source):
    return pd.read_csv(source)


def spreadsheet_upload_key(source, df):
    if isinstance(source, str):
        mtime = int(os.path.getmtime(source))
        return f"default:{os.path.basename(source)}:{mtime}:{len(df)}"
    size = getattr(source, "size", "")
    return f"{source.name}:{size}:{len(df)}"


def pick_default(candidates, columns):
    if not columns:
        return None

    normalized_columns = {
        str(column).strip().lower().replace("_", "").replace(" ", ""): column
        for column in columns
    }
    for candidate in candidates:
        if candidate in columns:
            return candidate
        normalized = str(candidate).strip().lower().replace("_", "").replace(" ", "")
        if normalized in normalized_columns:
            return normalized_columns[normalized]
    return None


def column_default(columns, index, fallback_candidates=None):
    candidate_match = pick_default(fallback_candidates or [], columns)
    if candidate_match is not None:
        return candidate_match
    if index < len(columns):
        return columns[index]
    return columns[0] if columns else None


def get_nonzero_values(row, value_cols, value_colors=None):
    values = []
    labels = []
    colors = []
    for idx, label in enumerate(value_cols):
        value = row[label]
        if pd.notnull(value) and value != 0:
            try:
                value = float(value)
            except Exception:
                continue
            values.append(value)
            labels.append(label)
            if value_colors is not None:
                colors.append(value_colors[idx] if idx < len(value_colors) else None)
    if value_colors is not None:
        return values, labels, colors
    return values, labels


def coordinate_column_errors(df, column, axis):
    """Return validation errors for a selected latitude/longitude column."""
    limits = {"latitude": (-90.0, 90.0), "longitude": (-180.0, 180.0)}
    if axis not in limits:
        raise ValueError(f"Unknown coordinate axis: {axis}")

    lower, upper = limits[axis]
    values = pd.to_numeric(df[column], errors="coerce")
    errors = []

    non_numeric = values.isna()
    if non_numeric.any():
        bad_count = int(non_numeric.sum())
        sample = df.loc[non_numeric, column].iloc[0]
        errors.append(
            f"'{column}' has {bad_count} non-numeric or empty {axis} value(s) "
            f"(example: {sample!r})"
        )

    out_of_range = values.notna() & ((values < lower) | (values > upper))
    if out_of_range.any():
        bad_count = int(out_of_range.sum())
        sample = float(values.loc[out_of_range].iloc[0])
        errors.append(
            f"'{column}' has {bad_count} {axis} value(s) outside {lower:g} to {upper:g} "
            f"(example: {sample:g})"
        )

    return errors
