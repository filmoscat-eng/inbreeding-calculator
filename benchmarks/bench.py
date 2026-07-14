from __future__ import annotations

import sys                              
import time                             
import tracemalloc                      
from pathlib import Path                



ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import compute_inbreeding, load_dataframe       
from benchmarks.synth import generate_pedigree            


def bench(n_founders: int, n_generations: int, offspring_per_gen: int) -> dict:
    """Прогнать один бенчмарк и вернуть метрики словарём.

    Один прогон:
    1. Сгенерировать DataFrame родословной.
    2. Замерить, сколько занимает её загрузка в Pedigree.
    3. Замерить, сколько занимает расчёт F (включая построение матрицы A).
    4. Записать пиковую память.
    5. Подсчитать сводные метрики (сколько инбредных, какой максимальный F).
    """
    df = generate_pedigree(n_founders, n_generations, offspring_per_gen)
    n = len(df)

    
    t0 = time.perf_counter()
    ped = load_dataframe(df)
    t_load = time.perf_counter() - t0

    
    
    tracemalloc.start()
    t0 = time.perf_counter()
    F = compute_inbreeding(ped)
    t_compute = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    
    
    
    nonzero = sum(1 for v in F.values() if v > 1e-12)
    max_F = max(F.values()) if F else 0.0

    return {
        "n": n,
        "n_founders": n_founders,
        "n_generations": n_generations,
        "t_load_s": round(t_load, 4),
        "t_compute_s": round(t_compute, 4),
        "peak_mem_mb": round(peak / 1024 / 1024, 2),
        "n_inbred": nonzero,
        "max_F": round(max_F, 4),
    }


def main() -> None:
    """Прогнать набор стандартных размеров и вывести таблицу."""
    cases = [
        (10, 5, 20),       
        (20, 8, 125),      
        (40, 10, 500),     
    ]
    print(f"{'n':>6} | {'load':>8} | {'compute':>10} | {'mem MB':>8} | {'inbred':>7} | {'maxF':>6}")
    print("-" * 60)
    for nf, ng, off in cases:
        r = bench(nf, ng, off)
        print(
            f"{r['n']:>6} | {r['t_load_s']:>8.3f} | {r['t_compute_s']:>10.3f} | "
            f"{r['peak_mem_mb']:>8.1f} | {r['n_inbred']:>7} | {r['max_F']:>6.3f}"
        )




if __name__ == "__main__":
    main()
