"""Эталонные примеры с известными значениями F (можно проверить на бумаге)."""

import math

import pytest

from core import (
    Pedigree,
    compute_inbreeding,
    compute_relationship_matrix,
    relationship,
    kinship,
    wright_paths,
)


def make(*entries):
    ped = Pedigree()
    for e in entries:
        if len(e) == 1:
            ped.add(e[0])
        else:
            ped.add(e[0], e[1], e[2])
    ped.validate()
    return ped


def test_founders_have_zero_F():
    ped = make(("A",), ("B",))
    F = compute_inbreeding(ped)
    assert F["A"] == 0.0
    assert F["B"] == 0.0


def test_full_sibs_offspring_has_F_025():
    """E = потомок полных сибсов C и D, у которых одни и те же родители A и B."""
    ped = make(
        ("A",), ("B",),
        ("C", "A", "B"),
        ("D", "A", "B"),
        ("E", "C", "D"),
    )
    F = compute_inbreeding(ped)
    assert math.isclose(F["E"], 0.25, abs_tol=1e-12)


def test_half_sibs_offspring_has_F_0125():
    """E = потомок полусибсов (общий отец A, разные матери B и D)."""
    ped = make(
        ("A",), ("B",), ("D",),
        ("C1", "A", "B"),
        ("C2", "A", "D"),
        ("E", "C1", "C2"),
    )
    F = compute_inbreeding(ped)
    assert math.isclose(F["E"], 0.125, abs_tol=1e-12)


def test_first_cousins_offspring_F_one_sixteenth():
    """Полные двоюродные — два общих прадеда (A, B). F потомка = 1/16."""
    ped = make(
        ("A",), ("B",),
        ("M1",), ("M2",),
        ("P1", "A", "B"),
        ("P2", "A", "B"),                    # P1 и P2 — полные сибсы
        ("X", "P1", "M1"),
        ("Y", "P2", "M2"),                   # X и Y — двоюродные
        ("E", "X", "Y"),
    )
    F = compute_inbreeding(ped)
    assert math.isclose(F["E"], 1 / 16, abs_tol=1e-12)


def test_first_cousins_single_common_ancestor():
    """Полудвоюродные (общий только один прадед A). F потомка = 1/32."""
    ped = make(
        ("A",),
        ("M1",), ("M2",), ("M3",), ("M4",),
        ("P1", "A", "M1"),
        ("P2", "A", "M2"),
        ("X", "P1", "M3"),
        ("Y", "P2", "M4"),
        ("E", "X", "Y"),
    )
    F = compute_inbreeding(ped)
    assert math.isclose(F["E"], 1 / 32, abs_tol=1e-12)


def test_father_daughter_offspring_F_025():
    ped = make(
        ("A",), ("B",),
        ("C", "A", "B"),
        ("E", "A", "C"),         # отец A × дочь C
    )
    F = compute_inbreeding(ped)
    assert math.isclose(F["E"], 0.25, abs_tol=1e-12)


def test_double_first_cousins():
    """Двойные двоюродные — F = 1/8."""
    ped = make(
        ("A",), ("B",), ("C",), ("D",),
        ("P1", "A", "B"),
        ("P2", "A", "B"),
        ("Q1", "C", "D"),
        ("Q2", "C", "D"),
        ("X", "P1", "Q1"),
        ("Y", "P2", "Q2"),
        ("E", "X", "Y"),
    )
    F = compute_inbreeding(ped)
    assert math.isclose(F["E"], 1 / 8, abs_tol=1e-12)


def test_wright_paths_match_tabular():
    """Метод Райта с разложением по путям должен давать ту же сумму, что и табличный."""
    ped = make(
        ("A",), ("B",),
        ("C", "A", "B"),
        ("D", "A", "B"),
        ("E", "C", "D"),
        ("F", "E", "D"),
        ("G", "F", "D"),
    )
    F = compute_inbreeding(ped)
    for ind in ("E", "F", "G"):
        wright_F, contribs = wright_paths(ped, ind, F)
        assert math.isclose(wright_F, F[ind], abs_tol=1e-10), (
            f"{ind}: Райт {wright_F} ≠ табличный {F[ind]}"
        )
        # Сумма вкладов = F
        assert math.isclose(sum(c.contribution for c in contribs), F[ind], abs_tol=1e-10)


def test_relationship_full_sibs():
    """Полные сибсы (родители — основатели): R = 0.5."""
    ped = make(
        ("A",), ("B",),
        ("C", "A", "B"),
        ("D", "A", "B"),
    )
    compute_relationship_matrix(ped)
    assert math.isclose(relationship(ped, "C", "D"), 0.5, abs_tol=1e-12)


def test_relationship_parent_child():
    """Родитель–потомок (родители-основатели): R = 0.5."""
    ped = make(
        ("A",), ("B",),
        ("C", "A", "B"),
    )
    compute_relationship_matrix(ped)
    assert math.isclose(relationship(ped, "A", "C"), 0.5, abs_tol=1e-12)


def test_kinship_self_equals_half_one_plus_F():
    ped = make(
        ("A",), ("B",),
        ("C", "A", "B"),
        ("D", "A", "B"),
        ("E", "C", "D"),
    )
    F = compute_inbreeding(ped)
    f_self = kinship(ped, "E", "E")
    assert math.isclose(f_self, 0.5 * (1 + F["E"]), abs_tol=1e-12)


def test_inbred_ancestor_increases_descendant_F():
    """Если общий предок сам инбредный, F потомка выше."""
    ped_simple = make(
        ("A",), ("B",),
        ("C", "A", "B"),
        ("D", "A", "B"),
        ("E", "C", "D"),
    )
    F_simple = compute_inbreeding(ped_simple)["E"]

    ped_inbred = make(
        ("A1",), ("B1",),
        ("A", "A1", "B1"),                   # неинбредный
        ("B", "A1", "B1"),                   # B и A — полные сибсы (R(A,B)=0.5)
        ("C", "A", "B"),                     # C сам инбредный
        ("D", "A", "B"),                     # D сам инбредный
        ("E", "C", "D"),                     # потомок двух инбредных полных сибсов
    )
    F_inbred = compute_inbreeding(ped_inbred)["E"]

    assert F_inbred > F_simple


# ------------------- валидаторы -------------------

def test_self_parent_raises():
    from core import SelfParentError

    ped = Pedigree()
    ped.add("X", father="X")
    with pytest.raises(SelfParentError):
        ped.validate()


def test_unknown_parent_raises():
    from core import UnknownParentError

    ped = Pedigree()
    ped.add("X", father="GHOST")
    with pytest.raises(UnknownParentError):
        ped.validate()


def test_same_parent_raises():
    from core import SameParentError

    ped = Pedigree()
    ped.add("Z")
    ped.add("X", father="Z", mother="Z")
    with pytest.raises(SameParentError):
        ped.validate()


def test_cycle_raises():
    from core import CycleError

    ped = Pedigree()
    # Конструируем цикл, обходя add() который сам по себе цикл не создать
    ped.individuals["A"] = {"father": "B", "mother": None}
    ped.individuals["B"] = {"father": "A", "mother": None}
    ped._invalidate_cache()
    with pytest.raises(CycleError):
        ped.validate()
