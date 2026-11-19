"""The catalogue, from code, as the deployment approves it."""

from __future__ import annotations

from rba.declaration import DECLARATION


def test_four_datasets_rates_and_prices() -> None:
    keys = [d.key for d in DECLARATION.catalogue]
    assert keys == ["rba_rates", "rba_curves", "rba_fx", "rba_restricted"]
    kinds = {d.key: list(d.data_types) for d in DECLARATION.catalogue}
    assert kinds["rba_fx"] == ["meridian.v1.Price"] and kinds["rba_curves"] == ["meridian.v1.Rate"]
    assert kinds["rba_restricted"] == ["meridian.v1.Rate", "meridian.v1.Price"]
    for dataset in DECLARATION.catalogue:
        assert dataset.day_time_zone == "Australia/Sydney"
        assert dataset.vendor == "Reserve Bank of Australia"
        assert dataset.gap_recovery == "backfill" and not dataset.calendar_id
        said = dataset.terms_and_pricing
        assert "Source: Reserve Bank of" in said and "benchmark" in said and len(said) <= 2000


def test_the_third_parties_columns_are_pulled_only_and_served_not_kept() -> None:
    modes = {d.key: list(d.modes) for d in DECLARATION.catalogue}
    push, pull = modes["rba_rates"]
    assert push != pull and modes["rba_curves"] == modes["rba_fx"] == [push, pull]
    assert modes["rba_restricted"] == [pull]
    restricted = DECLARATION.catalogue[3].terms_and_pricing
    assert "served, not kept" in restricted
    assert all(name in restricted for name in ("ASX", "FENICS", "WM/Reuters"))
    assert all("served, not kept" not in d.terms_and_pricing for d in DECLARATION.catalogue[:3])


def test_the_answers_are_kept_in_storage() -> None:
    assert DECLARATION.storage is not None
    assert [k.name for k in DECLARATION.storage.kinds] == ["responses"]
