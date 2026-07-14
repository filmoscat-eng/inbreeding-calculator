"""Тесты загрузки CSV/XLSX и нормализации колонок."""

import math
from pathlib import Path

import pandas as pd
import pytest

from core import compute_inbreeding, load_csv, load_dataframe


FIXTURES = Path(__file__).parent / "fixtures"


def test_load_csv_basic():
    ped = load_csv(FIXTURES / "pedigree_5.csv")
    F = compute_inbreeding(ped)
    assert math.isclose(F["E"], 0.25, abs_tol=1e-12)


def test_load_dataframe_with_aliases():
    df = pd.DataFrame(
        [
            {"animal": "A", "sire": None, "dam": None},
            {"animal": "B", "sire": None, "dam": None},
            {"animal": "C", "sire": "A", "dam": "B"},
        ]
    )
    ped = load_dataframe(df)
    assert "C" in ped
    assert ped.parents("C") == ("A", "B")


def test_load_dataframe_with_russian_columns():
    df = pd.DataFrame(
        [
            {"кличка": "A", "отец": "", "мать": ""},
            {"кличка": "B", "отец": "", "мать": ""},
            {"кличка": "C", "отец": "A", "мать": "B"},
        ]
    )
    ped = load_dataframe(df)
    assert ped.parents("C") == ("A", "B")


def test_empty_id_raises():
    df = pd.DataFrame([{"id": "", "father": None, "mother": None}])
    with pytest.raises(ValueError):
        load_dataframe(df)
