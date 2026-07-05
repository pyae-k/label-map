"""World Bank country-level baseline definitions for built-in map data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ValueKind = Literal["int", "float"]


@dataclass(frozen=True)
class WorldBankBaseline:
    """One static country-level baseline backed by World Bank data."""

    label: str
    value_column: str
    year: str
    value_kind: ValueKind
    csv_slug: str
    indicator: str | None = None
    derived_numerator: str | None = None
    derived_denominator: str | None = None

    @property
    def is_derived(self) -> bool:
        return self.derived_numerator is not None and self.derived_denominator is not None


def world_bank_source_label(baseline: WorldBankBaseline) -> str:
    """Build legend attribution matching the Population baseline style."""
    if baseline.is_derived:
        code = f"{baseline.derived_numerator} ÷ {baseline.derived_denominator}"
    else:
        code = baseline.indicator or ""
    return f"Source: World Bank ({code}, as of {baseline.year})"


# Snapshot years should be refreshed periodically as World Bank publishes updates.
# Tuple order is the Data source dropdown order (most-used indicators first).
_WORLD_BANK_BASELINES: tuple[WorldBankBaseline, ...] = (
    WorldBankBaseline(
        label="Population",
        value_column="Population",
        indicator="SP.POP.TOTL",
        year="2024",
        value_kind="int",
        csv_slug="population",
    ),
    WorldBankBaseline(
        label="GDP",
        value_column="GDP",
        indicator="NY.GDP.MKTP.CD",
        year="2023",
        value_kind="int",
        csv_slug="gdp",
    ),
    WorldBankBaseline(
        label="GDP per capita",
        value_column="GDP per capita",
        indicator="NY.GDP.PCAP.CD",
        year="2023",
        value_kind="float",
        csv_slug="gdp_per_capita",
    ),
    WorldBankBaseline(
        label="Life expectancy",
        value_column="Life expectancy",
        indicator="SP.DYN.LE00.IN",
        year="2023",
        value_kind="float",
        csv_slug="life_expectancy",
    ),
    WorldBankBaseline(
        label="CO2 emissions",
        value_column="CO2 emissions",
        indicator="EN.GHG.CO2.MT.CE.AR5",
        year="2021",
        value_kind="int",
        csv_slug="co2_emissions",
    ),
    WorldBankBaseline(
        label="Internet users",
        value_column="Internet users",
        indicator="IT.NET.USER.ZS",
        year="2023",
        value_kind="float",
        csv_slug="internet_users",
    ),
    WorldBankBaseline(
        label="Electricity access",
        value_column="Electricity access",
        indicator="EG.ELC.ACCS.ZS",
        year="2022",
        value_kind="float",
        csv_slug="electricity_access",
    ),
    WorldBankBaseline(
        label="Urban population",
        value_column="Urban population",
        indicator="SP.URB.TOTL",
        year="2024",
        value_kind="int",
        csv_slug="urban_population",
    ),
    WorldBankBaseline(
        label="Population density",
        value_column="Population density",
        year="2023",
        value_kind="float",
        csv_slug="population_density",
        derived_numerator="SP.POP.TOTL",
        derived_denominator="AG.LND.TOTL.K2",
    ),
    WorldBankBaseline(
        label="Literacy rate",
        value_column="Literacy rate",
        indicator="SE.ADT.LITR.ZS",
        year="2022",
        value_kind="float",
        csv_slug="literacy_rate",
    ),
    WorldBankBaseline(
        label="Unemployment",
        value_column="Unemployment",
        indicator="SL.UEM.TOTL.ZS",
        year="2023",
        value_kind="float",
        csv_slug="unemployment",
    ),
    WorldBankBaseline(
        label="Exports (% of GDP)",
        value_column="Exports (% of GDP)",
        indicator="NE.EXP.GNFS.ZS",
        year="2023",
        value_kind="float",
        csv_slug="exports_pct_gdp",
    ),
    WorldBankBaseline(
        label="Inflation",
        value_column="Inflation",
        indicator="FP.CPI.TOTL.ZG",
        year="2023",
        value_kind="float",
        csv_slug="inflation",
    ),
    WorldBankBaseline(
        label="Poverty headcount",
        value_column="Poverty headcount",
        indicator="SI.POV.DDAY",
        year="2021",
        value_kind="float",
        csv_slug="poverty_headcount",
    ),
    WorldBankBaseline(
        label="Gini index",
        value_column="Gini index",
        indicator="SI.POV.GINI",
        year="2021",
        value_kind="float",
        csv_slug="gini_index",
    ),
    WorldBankBaseline(
        label="Land area",
        value_column="Land area",
        indicator="AG.LND.TOTL.K2",
        year="2021",
        value_kind="int",
        csv_slug="land_area",
    ),
    WorldBankBaseline(
        label="Rural population",
        value_column="Rural population",
        indicator="SP.RUR.TOTL",
        year="2024",
        value_kind="int",
        csv_slug="rural_population",
    ),
    WorldBankBaseline(
        label="Arable land",
        value_column="Arable land",
        indicator="AG.LND.ARBL.ZS",
        year="2021",
        value_kind="float",
        csv_slug="arable_land",
    ),
    WorldBankBaseline(
        label="Forest area",
        value_column="Forest area",
        indicator="AG.LND.FRST.K2",
        year="2022",
        value_kind="int",
        csv_slug="forest_area",
    ),
    WorldBankBaseline(
        label="Renewable energy",
        value_column="Renewable energy",
        indicator="EG.FEC.RNEW.ZS",
        year="2021",
        value_kind="float",
        csv_slug="renewable_energy",
    ),
    WorldBankBaseline(
        label="Mobile subscriptions",
        value_column="Mobile subscriptions",
        indicator="IT.CEL.SETS.P2",
        year="2023",
        value_kind="float",
        csv_slug="mobile_subscriptions",
    ),
    WorldBankBaseline(
        label="Health expenditure",
        value_column="Health expenditure",
        indicator="SH.XPD.CHEX.GD.ZS",
        year="2021",
        value_kind="float",
        csv_slug="health_expenditure",
    ),
    WorldBankBaseline(
        label="School enrollment",
        value_column="School enrollment",
        indicator="SE.SEC.ENRR",
        year="2023",
        value_kind="float",
        csv_slug="school_enrollment",
    ),
    WorldBankBaseline(
        label="Infant mortality",
        value_column="Infant mortality",
        indicator="SP.DYN.IMRT.IN",
        year="2023",
        value_kind="float",
        csv_slug="infant_mortality",
    ),
    WorldBankBaseline(
        label="Fertility rate",
        value_column="Fertility rate",
        indicator="SP.DYN.TFRT.IN",
        year="2023",
        value_kind="float",
        csv_slug="fertility_rate",
    ),
    WorldBankBaseline(
        label="Military expenditure",
        value_column="Military expenditure",
        indicator="MS.MIL.XPND.GD.ZS",
        year="2022",
        value_kind="float",
        csv_slug="military_expenditure",
    ),
    WorldBankBaseline(
        label="Tourism arrivals",
        value_column="Tourism arrivals",
        indicator="ST.INT.ARVL",
        year="2019",
        value_kind="int",
        csv_slug="tourism_arrivals",
    ),
)

WORLD_BANK_BASELINE_BY_LABEL = {baseline.label: baseline for baseline in _WORLD_BANK_BASELINES}
WORLD_BANK_BASELINE_LABELS = [baseline.label for baseline in _WORLD_BANK_BASELINES]
