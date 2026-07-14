from __future__ import annotations

import random                  

import pandas as pd            


def generate_pedigree(
    n_founders: int,
    n_generations: int,
    offspring_per_generation: int,
    seed: int = 42,
) -> pd.DataFrame:
    """Сгенерировать родословную с заданными параметрами.

    Параметры:
    - n_founders — сколько основателей (поколение 0).
    - n_generations — сколько последующих поколений построить.
    - offspring_per_generation — сколько особей создавать в каждом поколении.
    - seed — фиксированное зерно для воспроизводимости.

    Каждое следующее поколение получается случайным скрещиванием особей
    из предыдущего поколения. Без скрещиваний между поколениями — это упрощение,
    но даёт реалистичный «прорастающий» инбридинг.
    """
    
    
    rng = random.Random(seed)
    rows: list[dict[str, str | None]] = []
    
    generations: list[list[str]] = [[]]

    
    for i in range(n_founders):
        
        
        ind = f"F{i:04d}"
        rows.append({"id": ind, "father": None, "mother": None})
        generations[0].append(ind)

    
    for g in range(1, n_generations + 1):
        prev_gen = generations[g - 1]
        
        if len(prev_gen) < 2:
            break
        
        
        
        pool_males = prev_gen
        pool_females = prev_gen

        gen: list[str] = []
        for k in range(offspring_per_generation):
            father = rng.choice(pool_males)
            mother = rng.choice(pool_females)
            
            while mother == father:
                mother = rng.choice(pool_females)
            ind = f"G{g:02d}_{k:04d}"
            rows.append({"id": ind, "father": father, "mother": mother})
            gen.append(ind)
        generations.append(gen)

    return pd.DataFrame(rows)


def preset(size: str) -> pd.DataFrame:
    """Готовые наборы для бенчмарка.

    Используется в бенчмарках, чтобы один и тот же «эталонный» размер
    можно было получить одной строкой.
    """
    presets = {
        "small": (10, 4, 20),         
        "medium": (20, 8, 125),       
        "large": (40, 10, 1000),      
    }
    nf, ng, off = presets[size]
    return generate_pedigree(nf, ng, off)
