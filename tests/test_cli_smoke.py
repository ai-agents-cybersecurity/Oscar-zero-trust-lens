from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from oscal_zt import cli


class FakeReport:
    def model_dump(self):
        return {
            "coverage_by_dimension": {"identity": 50.0},
            "missing_core_controls": {"identity": ["AC-2"]},
            "summary": "Stub summary",
            "gaps": [],
        }


class FakeGraph:
    def invoke(self, _state):
        return {"zt_report": FakeReport(), "annotated_controls": []}


def test_help_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["oscal-zt", "--help"])

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 0


def test_json_happy_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    catalog = tmp_path / "catalog.json"
    catalog.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["oscal-zt", "--json", "--catalog", str(catalog)])
    monkeypatch.setattr(cli, "load_catalog_controls", lambda _path: [])
    monkeypatch.setattr(cli, "build_graph", lambda: FakeGraph())

    cli.main()

    out = capsys.readouterr().out
    assert '"summary": "Stub summary"' in out


def test_missing_catalog_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.json"
    monkeypatch.setattr(sys, "argv", ["oscal-zt", "--catalog", str(missing)])

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 1
