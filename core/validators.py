from __future__ import annotations



from typing import Iterable, Mapping






class PedigreeError(Exception):
    """Базовое исключение для всех ошибок родословной.

    UI ловит именно его, чтобы единообразно обработать любую ошибку валидации:
    `except PedigreeError as e: st.error(str(e))`.

    Все более конкретные ошибки наследуются от него — это даёт нам две степени
    точности обработки: общая (PedigreeError для «любая проблема с данными»)
    и специфичная (DuplicateIdError для «именно дубли»).
    """
    
    


class DuplicateIdError(PedigreeError):
    """Один и тот же ID особи встречается в данных дважды или больше."""

    def __init__(self, ids: Iterable[str]) -> None:
        
        
        
        
        self.ids = list(ids)
        
        
        super().__init__(f"Дублирующиеся ID особей: {self.ids}")


class SelfParentError(PedigreeError):
    """Особь указана как собственный отец или мать.

    Биологически невозможно. Чаще всего — опечатка в данных
    (скопировали ID не в ту колонку).
    """

    def __init__(self, individual: str) -> None:
        
        self.individual = individual
        super().__init__(f"Особь '{individual}' указана как собственный родитель")


class UnknownParentError(PedigreeError):
    """Указанный родитель отсутствует среди ID родословной.

    Это либо опечатка в ID, либо неполные данные (родителя «не дозагрузили»).
    Программа не может посчитать вклад особи, которой у неё нет.
    """

    def __init__(self, individual: str, parent: str) -> None:
        self.individual = individual    
        self.parent = parent            
        super().__init__(
            f"Особь '{individual}' ссылается на несуществующего родителя '{parent}'"
        )


class SameParentError(PedigreeError):
    """Отец и мать у особи совпадают (биологически невозможно).

    Не путать с самооплодотворением у растений — там просто отец = мать = X,
    но это валидно. У нас же это всегда ошибка ввода.
    """

    def __init__(self, individual: str, parent: str) -> None:
        self.individual = individual
        self.parent = parent
        super().__init__(
            f"У особи '{individual}' отец и мать совпадают: '{parent}'"
        )


class CycleError(PedigreeError):
    """В родословной найден цикл: потомок становится своим же предком.

    В реальной биологии невозможно (нарушает причинность), но возникает
    из-за опечаток в данных. Например, перепутали потомка и родителя.
    """

    def __init__(self, cycle: Iterable[str]) -> None:
        
        self.cycle = list(cycle)
        
        super().__init__(f"Обнаружен цикл в родословной: {' -> '.join(self.cycle)}")








def check_duplicates(ids: Iterable[str]) -> None:
    """Проверить, что среди ID нет повторов.

    Алгоритм: идём по списку ID и запоминаем уже встреченные в `seen`. Любой ID,
    встреченный повторно, попадает в список `duplicates`. По завершении прохода,
    если набралось хоть что-то — кидаем DuplicateIdError со всем списком.

    Сложность O(n). Поиск в set() — O(1) в среднем.
    """
    seen: set[str] = set()         
    duplicates: list[str] = []     
    for i in ids:
        if i in seen:
            
            duplicates.append(i)
        
        
        seen.add(i)
    if duplicates:
        
        raise DuplicateIdError(duplicates)


def check_self_parent(individuals: Mapping[str, dict]) -> None:
    """Никто не должен быть собственным отцом или матерью.

    Проверка простая: для каждой особи смотрим оба её родителя и сравниваем
    с её же ID. Достаточно одного совпадения, чтобы кинуть исключение.
    """
    for ind, rec in individuals.items():
        
        if rec["father"] == ind or rec["mother"] == ind:
            raise SelfParentError(ind)


def check_known_parents(individuals: Mapping[str, dict]) -> None:
    """Если у особи указан родитель, он должен присутствовать в родословной.

    Тонкость: пустое поле (None) — это «основатель», т.е. родитель неизвестен.
    Это допустимо. А вот ссылка на ID, которого в данных нет, — ошибка.

    Алгоритм: для каждой особи смотрим оба её родителя; если родитель
    не None и его ID нет в множестве известных особей — кидаем исключение.
    """
    for ind, rec in individuals.items():
        for role in ("father", "mother"):
            parent = rec[role]
            
            
            if parent is not None and parent not in individuals:
                raise UnknownParentError(ind, parent)


def check_same_parents(individuals: Mapping[str, dict]) -> None:
    """Отец и мать не должны быть одной и той же особью.

    Если оба родителя пустые (None) — это просто основатель, всё нормально.
    Совпадение «оба None» исключаем условием `f is not None` (None == None
    тоже True, но тогда и check_self_parent уже бы кинула, так что эта
    проверка работает только для случая «оба указаны, но одинаковые»).
    """
    for ind, rec in individuals.items():
        f, m = rec["father"], rec["mother"]
        if f is not None and f == m:
            raise SameParentError(ind, f)






def topological_sort(individuals: Mapping[str, dict]) -> list[str]:
    """Алгоритм Кана: вернуть особей в порядке «родители раньше потомков».

    Зачем нужен этот порядок:
    - Табличный метод Хендерсона требует, чтобы при обработке особи i все
      её j < i были уже посчитаны. Это значит «родители раньше потомков».
    - Заодно алгоритм обнаруживает циклы: если по окончании остались особи
      с ненулевой входящей степенью — где-то есть петля.

    Идея алгоритма:
    1. Для каждой особи считаем «входящую степень» — сколько у неё родителей,
       присутствующих в родословной (0, 1 или 2).
    2. В очередь кладём всех с входящей степенью 0 — это основатели.
    3. По очереди достаём из очереди особь, добавляем в результирующий список.
       У всех её детей уменьшаем входящую степень на 1; если у ребёнка стало 0,
       значит все его родители уже обработаны → кладём в очередь.
    4. Если в конце результирующий список короче исходного множества — значит
       часть особей застряла из-за цикла, кидаем CycleError.

    Сложность: O(V + E) — каждая вершина и каждое ребро обрабатываются один раз.
    Для нашей задачи V = число особей, E ≤ 2V (каждая особь имеет максимум
    2 родителя), так что это O(n).
    """
    
    
    indegree: dict[str, int] = {ind: 0 for ind in individuals}

    
    
    
    
    children: dict[str, list[str]] = {ind: [] for ind in individuals}

    
    for ind, rec in individuals.items():
        for role in ("father", "mother"):
            parent = rec[role]
            if parent is not None:
                indegree[ind] += 1            
                children[parent].append(ind)  

    
    
    queue = [ind for ind, deg in indegree.items() if deg == 0]
    order: list[str] = []  

    
    
    
    while queue:
        
        
        
        node = queue.pop(0)
        order.append(node)
        
        for child in children[node]:
            indegree[child] -= 1
            if indegree[child] == 0:
                
                queue.append(child)

    
    if len(order) != len(individuals):
        
        
        remaining = [ind for ind, deg in indegree.items() if deg > 0]
        raise CycleError(_extract_cycle(individuals, remaining))

    
    return order


def _extract_cycle(individuals: Mapping[str, dict], suspects: list[str]) -> list[str]:
    """Извлечь конкретный цикл из набора подозрительных вершин.

    Это эвристика для красивого сообщения об ошибке. Точный поиск всех циклов —
    дорогая задача; нам же достаточно показать пользователю один пример.

    Эвристика: стартуем с любой подозрительной вершины, идём по родительским
    ссылкам, пока не вернёмся в уже посещённую — это и будет цикл. Метод
    не идеален (может вернуть лишь один из нескольких циклов, или промахнуться
    на сложной топологии), но для диагностики и сообщения пользователю этого хватает.
    """
    if not suspects:
        return []
    start = suspects[0]
    path: list[str] = []           
    visited: set[str] = set()      
    current: str | None = start

    
    
    
    
    
    while current is not None and current not in visited:
        visited.add(current)
        path.append(current)
        rec = individuals[current]
        
        
        nxt = rec["father"] if rec["father"] in suspects else rec["mother"]
        current = nxt if nxt in suspects else None

    if current is not None:
        
        
        
        idx = path.index(current)
        return path[idx:] + [current]
    
    return path






def validate_all(individuals: Mapping[str, dict]) -> list[str]:
    """Запустить все проверки и вернуть топологический порядок.

    Порядок проверок ВАЖЕН:

    - Дубли проверяем первыми, потому что дальше работаем со словарём — там
      дубликаты ID уже исчезли (словарь по определению хранит каждый ключ
      один раз), и без явной проверки мы их не заметим.

    - Само-родители раньше неизвестных родителей: при само-родительстве
      родитель формально известен (это сама особь), и проверка
      «неизвестный родитель» промахнётся — нужна отдельная.

    - Циклы — последними: для остальных проверок цикл не мешает, а топосорт
      всё равно нужен как побочный продукт (порядок особей).
    """
    
    check_duplicates(list(individuals.keys()))
    
    check_self_parent(individuals)
    
    check_known_parents(individuals)
    
    check_same_parents(individuals)
    
    return topological_sort(individuals)
