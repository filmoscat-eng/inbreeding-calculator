from __future__ import annotations
import math
from typing import Optional
import numpy as np
import pandas as pd
from .validators import validate_all






def _normalize_id(value) -> Optional[str]:
    """Привести произвольное значение к строковому ID или None для пропусков.

    Зачем это нужно. Когда CSV/XLSX читает pandas, пустые ячейки превращаются
    в float NaN, а не в None. Если такое значение положить «как есть» и
    потом сделать str(NaN), получится строка "nan" — и валидация решит,
    что есть особь с таким ID. Это был реальный баг на ранних этапах разработки.

    Поэтому нужно явно ловить все «пустые» формы:
    - None (явный)
    - NaN (от pandas)
    - пустая строка (после чтения CSV)
    - прочерки и спец-маркеры (—, -, "None", "null", "nan" текстом)
    — и приводить их все к None.

    Эта функция — единая точка нормализации внутри Pedigree.add(): любое
    значение проходит через неё. Аналогичная функция _clean_value в io.py
    делает то же самое для DataFrame-уровня; они дублируются ради
    устойчивости (если кто-то построит Pedigree вручную, минуя io).
    """
    
    if value is None:
        return None
    
    
    if isinstance(value, float) and math.isnan(value):
        return None
    
    s = str(value).strip()
    
    
    if not s or s.lower() in ("nan", "none", "null", "—", "-"):
        return None
    
    return s






class Pedigree:
    """Родословная: множество особей с указанием отца и матери.

    Внутреннее представление:
    - `individuals: dict[str, dict]` — основное хранилище.
       Ключ — ID особи, значение — словарь {father, mother}.
       Используем dict, а не list, потому что нам нужен O(1) доступ по ID.

    - `_order: list[str] | None` — топологический порядок (заполняется validate()).
       None означает «ещё не считали» — будем считать при первом обращении.

    - `_index: dict[str, int] | None` — обратное отображение «ID → позиция в order».
       Нужно, чтобы быстро находить строку особи в матрице A.

    - `_A: np.ndarray | None` — матрица родства, заполняется extern. модулем
       (compute_relationship_matrix). Pedigree не считает её сам, но кэширует.

    - `_F: np.ndarray | None` — вектор инбридинга (диагональ A − 1).
       Заполняется автоматически при установке матрицы A.
    """

    def __init__(self) -> None:
        """Создать пустую родословную."""
        
        
        self.individuals: dict[str, dict] = {}
        
        
        self._order: list[str] | None = None
        self._index: dict[str, int] | None = None
        self._A: np.ndarray | None = None
        self._F: np.ndarray | None = None

    
    
    

    def add(
        self,
        individual: str,
        father: Optional[str] = None,
        mother: Optional[str] = None,
    ) -> None:
        """Добавить или перезаписать запись об особи.

        Аргументы:
        - individual: ID особи (обязательно).
        - father: ID отца или None (для основателей).
        - mother: ID матери или None.

        Семантика: если особь с таким ID уже была — её запись перезаписывается.
        Это позволяет легко исправлять данные: ped.add("X", father="A2") —
        и старая запись X с другим отцом просто заменилась.

        Любое изменение состава сбрасывает кэш — это безопасно и предсказуемо.
        """
        
        
        ind = _normalize_id(individual)
        if ind is None:
            
            
            
            raise ValueError("ID особи не может быть пустым")
        
        
        self._invalidate_cache()
        
        self.individuals[ind] = {
            "father": _normalize_id(father),
            "mother": _normalize_id(mother),
        }

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> "Pedigree":
        """Построить Pedigree из pandas DataFrame с колонками id/father/mother.

        Сразу запускает validate(), чтобы пользователь получил ошибку как можно
        ближе к месту загрузки, а не где-то глубоко в расчёте.

        Это «классовый метод» (classmethod), а не обычный конструктор, потому
        что он альтернативный способ построения. Стандартный путь —
        `ped = Pedigree(); ped.add(...)`. Этот — для готовых данных в DataFrame.
        """
        ped = cls()  
        
        
        
        for _, row in df.iterrows():
            ped.add(row["id"], row.get("father"), row.get("mother"))
        
        
        
        ped.validate()
        return ped

    
    
    

    def __len__(self) -> int:
        """len(ped) → число особей.

        Стандартный «магический метод» — позволяет писать `len(ped)` вместо
        `len(ped.individuals)`. Маленькое удобство, но из таких удобств
        складывается ощущение «чистого API».
        """
        return len(self.individuals)

    def __contains__(self, ind: str) -> bool:
        """`'X' in ped` → есть ли особь с таким ID.

        Тоже магический метод. Позволяет красиво писать проверки:
        `if 'A' in ped: ...` вместо `if 'A' in ped.individuals: ...`.
        """
        return ind in self.individuals

    def ids(self) -> list[str]:
        """Список всех ID в порядке вставки.

        Внимание: это НЕ топологический порядок. Для топологии используйте
        свойство `order`. Здесь же — порядок, в котором особей добавляли
        в родословную.
        """
        
        
        return list(self.individuals.keys())

    def parents(self, ind: str) -> tuple[Optional[str], Optional[str]]:
        """Вернуть пару (отец, мать). None означает основателя по этой линии.

        Удобный аксессор: вместо `ped.individuals[x]["father"], ped.individuals[x]["mother"]`
        пишем `father, mother = ped.parents(x)`.
        """
        rec = self.individuals[ind]
        return rec["father"], rec["mother"]

    def founders(self) -> list[str]:
        """Особи без обоих родителей — корни родословной.

        Полезно для статистики (сколько у нас «начальных» особей) и для
        визуализации (граф рисуем от основателей вниз).
        """
        return [
            ind
            for ind, rec in self.individuals.items()
            if rec["father"] is None and rec["mother"] is None
        ]

    def ancestors(self, ind: str) -> set[str]:
        """Все предки особи (без неё самой).

        Реализация через стек (а не рекурсию), чтобы не упереться в лимит
        рекурсии Python на больших родословных. Стек хранит «вершины,
        которые осталось обойти».

        Защита от двойной обработки одной вершины (важно для инбредных
        родословных, где один предок появляется в нескольких ветках):
        проверяем `parent not in result` перед добавлением в стек.
        Без этой проверки на инбредной родословной мы могли бы обходить
        одного и того же предка много раз.
        """
        result: set[str] = set()    
        stack = [ind]               
        while stack:
            current = stack.pop()
            for parent in self.parents(current):
                
                
                if parent is not None and parent not in result:
                    result.add(parent)
                    
                    stack.append(parent)
        return result

    
    
    

    def validate(self) -> list[str]:
        """Проверить все инварианты и пересобрать топологический порядок.

        Возвращает порядок, в котором родители всегда раньше потомков —
        он нужен табличному методу Хендерсона.

        Эта функция вызывается:
        - явно пользователем (если хочет сразу узнать об ошибках);
        - автоматически из from_dataframe (тоже для ранней ошибки);
        - лениво из свойств order/index (если пользователь сразу полез считать).
        """
        
        
        self._order = validate_all(self.individuals)
        
        
        
        self._index = {ind: i for i, ind in enumerate(self._order)}
        return self._order

    @property
    def order(self) -> list[str]:
        """Ленивое получение топологического порядка.

        Если validate() ещё не вызывался — вызовем его сейчас. Это удобно
        для интерактивного использования: пользователь может не помнить,
        что нужно явно валидировать.
        """
        if self._order is None:
            self.validate()
        
        
        assert self._order is not None
        return self._order

    @property
    def index(self) -> dict[str, int]:
        """Ленивое получение обратного индекса ID → позиция."""
        if self._index is None:
            self.validate()
        assert self._index is not None
        return self._index

    
    
    

    def _invalidate_cache(self) -> None:
        """Сбросить все производные структуры — вызывается при любых изменениях.

        Подчёркивание в начале имени = «приватный метод», не часть публичного
        API. Вызывается только изнутри Pedigree.add(). Извне этот метод
        тоже доступен (Python не запрещает), но обычно не нужен.
        """
        self._order = None
        self._index = None
        self._A = None
        self._F = None

    def set_relationship_matrix(self, A: np.ndarray) -> None:
        """Сохранить вычисленную матрицу A и сразу пересчитать F из её диагонали.

        F(i) = A[i,i] − 1 — это и есть «диагональный» способ извлечь F
        из матрицы родства, который даёт табличный метод.

        np.diag(A) возвращает массив диагональных элементов (не делая копию).
        """
        self._A = A
        self._F = np.diag(A) - 1.0

    def get_relationship_matrix(self) -> Optional[np.ndarray]:
        """Вернуть кэшированную матрицу A или None, если ещё не считалась.

        Возвращает именно None (а не кидает исключение или считает на лету),
        чтобы вызывающий код мог сам решить: «нужна, давай посчитаем» или
        «не нужна, не трогай».
        """
        return self._A

    def get_inbreeding_array(self) -> Optional[np.ndarray]:
        """Вернуть кэшированный вектор F (в порядке self.order) или None."""
        return self._F

    
    
    

    def to_dataframe(self) -> pd.DataFrame:
        """Сериализовать обратно в DataFrame — удобно для экспорта/превью.

        None заменяем пустой строкой, чтобы CSV выглядел привычно
        (стандартный CSV-конвенция: пустое значение = пустая клетка).
        """
        rows = []
        for ind, rec in self.individuals.items():
            rows.append(
                {"id": ind, "father": rec["father"] or "", "mother": rec["mother"] or ""}
            )
        return pd.DataFrame(rows)

    def __repr__(self) -> str:
        """Короткое представление для отладки в REPL/логах.

        Магический метод — то, что показывается в Python REPL при наборе
        имени переменной. Стандартный формат: ИмяКласса(ключевая_инфа).
        """
        return f"Pedigree(n={len(self)}, founders={len(self.founders())})"
