from __future__ import annotations



from pathlib import Path

from typing import Iterable


import pandas as pd


from .pedigree import Pedigree

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "id": ("id", "animal", "name", "individual", "ид", "имя", "кличка"),
    "father": ("father", "sire", "papa", "отец", "папа", "сир"),
    "mother": ("mother", "dam", "mama", "мать", "мама", "дам"),
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Привести имена колонок к id/father/mother. Лишние колонки отбрасываем.

    Алгоритм:
    1. Для каждой колонки исходного DataFrame проверяем, не алиас ли это
       какого-то канонического имени.
    2. Строим словарь переименований {старое: новое}.
    3. Применяем rename.
    4. Проверяем, что обязательная колонка id есть; колонки father/mother
       при отсутствии добавляем как пустые.
    5. Возвращаем только три нужные колонки в каноническом порядке.

    Если в исходном DataFrame есть, например, `Кличка` и `Дата рождения`,
    мы возьмём `Кличка` как id, а лишнее проигнорируем — это позволяет
    подсунуть программе живой экспорт из родословной книги, где много
    лишних столбцов.

    Тонкость: один canonical может быть занят только один раз. Если в
    DataFrame есть и `id`, и `animal` — возьмём первый встретившийся.
    Это сделано через множество `seen`.
    """
    rename: dict[str, str] = {}      
    seen: set[str] = set()           
    for col in df.columns:
        
        
        low = str(col).strip().lower()
        for canonical, aliases in COLUMN_ALIASES.items():
            if low in aliases and canonical not in seen:
                rename[col] = canonical
                seen.add(canonical)
                break  
    
    df = df.rename(columns=rename)

    
    missing = [c for c in ("id", "father", "mother") if c not in df.columns]
    if "id" in missing:
        
        
        raise ValueError(
            "Не найдена колонка с идентификатором особи. "
            f"Ожидаются варианты: {COLUMN_ALIASES['id']}"
        )
    
    
    for c in ("father", "mother"):
        if c not in df.columns:
            df[c] = None
    
    
    return df[["id", "father", "mother"]].copy()


def _clean_value(v):
    """Привести произвольное значение ячейки к строке или None.

    Зачем нужна эта функция отдельно от _normalize_id в pedigree.py:
    тут мы работаем с DataFrame, и pandas нам подсовывает свои NaN.
    Возвращать всегда нужно либо строку, либо None — это контракт add().

    Случаи:
    1. None — явный пропуск.
    2. NaN — pandas-вариант пропуска (в pandas нет различия None/NaN
       для object-колонок, и pd.isna() их объединяет).
    3. Пустая строка — после strip() остаётся "".
    4. Текстовые маркеры пустоты («nan», «none», «—», «-») — иногда
       встречаются в CSV, особенно если файл редактировали в Excel.
    """
    if v is None:
        return None
    
    
    
    if isinstance(v, float) and pd.isna(v):
        return None
    s = str(v).strip()
    
    if not s or s.lower() in ("nan", "none", "null", "—", "-"):
        return None
    return s






def load_dataframe(df: pd.DataFrame) -> Pedigree:
    """Построить Pedigree из произвольного DataFrame.

    Шаги:
    1. Нормализуем колонки (алиасы) — теперь точно есть id/father/mother.
    2. Чистим значения через _clean_value — превращаем NaN/«—»/«» в None.
    3. Проверяем, что в id нет пустых (это критическая ошибка).
    4. Передаём управление Pedigree.from_dataframe (он сам валидирует).

    Эта функция — общий вход для всех IO-источников. И load_csv, и load_excel
    в итоге вызывают её, отличаясь только тем, как читать файл.
    """
    df = _normalize_columns(df)
    
    
    df["id"] = df["id"].map(_clean_value)
    df["father"] = df["father"].map(_clean_value)
    df["mother"] = df["mother"].map(_clean_value)

    
    
    if df["id"].isna().any():
        raise ValueError("В колонке 'id' есть пустые значения")

    return Pedigree.from_dataframe(df)


def load_csv(path: str | Path, **kwargs) -> Pedigree:
    """Загрузить родословную из CSV-файла.

    Доп. **kwargs пробрасываются в pandas.read_csv — можно указать
    свой разделитель, кодировку и т.д., если файл нестандартный:

        load_csv("file.csv", sep=";", encoding="cp1251")
    """
    df = pd.read_csv(path, **kwargs)
    return load_dataframe(df)


def load_excel(path: str | Path, sheet_name: str | int = 0, **kwargs) -> Pedigree:
    """Загрузить родословную из XLSX/XLS-файла.

    sheet_name по умолчанию = 0 (первый лист). Если родословная на другом
    листе — можно передать имя или номер:

        load_excel("data.xlsx", sheet_name="Pedigree")
        load_excel("data.xlsx", sheet_name=2)

    Требует установленный openpyxl (для .xlsx) или xlrd (для старого .xls).
    """
    df = pd.read_excel(path, sheet_name=sheet_name, **kwargs)
    return load_dataframe(df)


def to_dataframe(ped: Pedigree, with_F: dict[str, float] | None = None) -> pd.DataFrame:
    """Сериализовать родословную обратно в DataFrame, опционально с колонкой F.

    Удобно для экспорта результатов в CSV/XLSX из Streamlit-приложения
    или из своего скрипта.

    Если передан with_F — добавляется колонка F с коэффициентами инбридинга
    каждой особи. Удобно для итогового отчёта.
    """
    df = ped.to_dataframe()
    if with_F is not None:
        
        
        df["F"] = df["id"].map(with_F).astype(float)
    return df


def iter_individuals(df: pd.DataFrame) -> Iterable[tuple[str, str | None, str | None]]:
    """Итератор для отладки: пройтись по всем особям нормализованного DataFrame.

    Не используется самим расчётом, но удобен в тестах и REPL-сессиях,
    когда хочется быстро посмотреть, что распарсилось из файла.

    yield вместо return — это генератор: значения отдаются по одному,
    память не тратится на построение полного списка.
    """
    df = _normalize_columns(df)
    for _, row in df.iterrows():
        yield (
            _clean_value(row["id"]),
            _clean_value(row["father"]),
            _clean_value(row["mother"]),
        )
