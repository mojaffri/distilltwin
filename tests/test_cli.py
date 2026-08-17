from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from distilltwin import cli


def test_cli_exports_a_reproducible_scenario(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    output = tmp_path / "nested" / "scenario.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "distilltwin",
            "--duration",
            "2",
            "--disturbance-at",
            "1",
            "--feed-composition",
            "0.62",
            "--sensor-bias",
            "0.03",
            "--output",
            str(output),
        ],
    )

    cli.main()

    exported = pd.read_csv(output)
    assert output.exists()
    assert len(exported) == 21
    assert exported["time"].iloc[[0, -1]].tolist() == [0.0, 2.0]
    assert exported.loc[exported["time"] >= 1.0, "feed_composition"].eq(0.62).all()
    assert "wrote 21 samples" in capsys.readouterr().out
