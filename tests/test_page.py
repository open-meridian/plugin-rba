"""The two pages under Manage, and their read tools."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from meridian.suites import Recorder
from meridian.testing import PageClient

from rba import page as page_module
from rba.page import CONNECTION, DATASETS_PAGE, figures, hold, pages

from conftest import AUD, HELD, INSTANCE, RESTRICTED, feed, fx_want, resolving, want


@pytest.fixture
def client(tmp_path: Path) -> PageClient:
    plugin = resolving(Recorder(INSTANCE), "OIS")
    work = feed(tmp_path, plugin)
    asyncio.run(work.check())
    for asked in (
        fx_want("w-usd", "2026-11-18", RESTRICTED),
        want("w-c", [HELD["Cash Rate Target"]], day="2026-10-01"),
    ):
        plugin.answer("ObservationsWanted", lambda _, w=asked: w.message)  # type: ignore[misc]
        asyncio.run(plugin.hear(work))
    hold(work)
    return PageClient(pages)


def test_each_page_is_managed_alone(client: PageClient) -> None:
    served = {(r.page.path, r.level): r.response.status for r in client.every_page()}
    assert served == {
        (CONNECTION, "admin"): 200,
        (CONNECTION, "write"): 403,
        (CONNECTION, "read"): 403,
        (DATASETS_PAGE, "admin"): 200,
        (DATASETS_PAGE, "write"): 403,
        (DATASETS_PAGE, "read"): 403,
    }
    client.assert_no_account_data("0.6115", "147.554507", "5.044", "0.6739")


def test_connection_and_its_tables(client: PageClient) -> None:
    text = client.get(CONNECTION, "admin").text
    assert "No key needed" in text and "Does not stream" in text and "1 record not held" in text
    sources = client.get(CONNECTION, "admin", tab="sources").text
    assert sources.count("<tr data-source=") == 4
    assert "Thu 19 Nov 2026" in sources and "Fri 30 Oct 2026" in sources
    assert sources.count("served, not kept") == 2


def test_datasets_and_records(client: PageClient) -> None:
    text = client.get(DATASETS_PAGE, "admin").text
    assert all(f"rba:{k}" in text for k in ("rba_rates", "rba_curves", "rba_fx", "rba_restricted"))
    assert "<h2>Wants</h2>" not in text and "<h2>Served</h2>" in text
    wants = client.get(DATASETS_PAGE, "admin", tab="wants").text
    assert "<h2>Wants</h2>" in wants and "<h2>Subjects</h2>" in wants
    records = client.get(DATASETS_PAGE, "admin", tab="records").text
    assert 'data-code="Cash Rate Target"' in records and 'data-code="EUR"' in records
    assert 'data-code="FXRTWI"' in records and "Source: Reserve Bank of Australia" in records
    assert client.get(DATASETS_PAGE, "admin", q="USD").text.count("<tr data-code=") == 1


def test_the_tools_answer_what_the_pages_show(client: PageClient) -> None:
    data = client.call_tool("read_connection").data
    assert data["mode"] == "Sample data" and [s["kind"] for s in data["sources"]] == [
        "F1", "F2", "F17", "F11.1",
    ]  # fmt: skip
    read = client.call_tool("read_datasets").data
    held = {r["code"]: r for r in read["records"]}
    assert held["Cash Rate Target"]["instrument_id"] == HELD["Cash Rate Target"]
    assert held["OIS"]["miss"] == "not held: reported missing"
    assert held["USD"]["dataset"] == "rba_restricted" and held["USD"]["instrument_id"] == AUD
    assert held["USD"]["latest_day"] == "2026-11-18" and held["EUR"]["dataset"] == "rba_fx"
    assert held["FZCY0D"]["miss"] == "not carried"


def test_before_the_first_check_and_not_reached(tmp_path: Path) -> None:
    page_module._held.clear()
    assert "Checking the RBA" in PageClient(pages).get(CONNECTION, "admin").text
    work = feed(tmp_path)
    work.status.sources["F1"].error = "https://www.rba.gov.au/statistics: URLError"
    hold(work)
    text = PageClient(pages).get(CONNECTION, "admin").text
    assert 'state="error"' in text and "Not answering" in text


def test_the_figures_are_the_data_roles(client: PageClient) -> None:
    work = page_module._held["feed"]
    said = figures(work.status, work)
    assert [f.label for f in said][:3] == ["Connection", "Entitled at the vendor", "Stream"]
