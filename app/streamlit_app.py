from __future__ import annotations

import sys                                  
from pathlib import Path                    

import pandas as pd                         
import streamlit as st                      



ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import (  
    Pedigree,
    PedigreeError,
    classify_inbreeding,
    compute_inbreeding,
    compute_relationship_matrix,
    kinship,
    load_dataframe,
    relationship,
    wright_paths,
)
from benchmarks.synth import generate_pedigree  






def build_dot(ped: Pedigree, root: str, depth: int, F: dict[str, float]) -> str:
    """Сформировать DOT-описание графа родословной от особи root вверх.

    Параметры:
    - ped — объект родословной.
    - root — особь, от которой растим граф (пробанд).
    - depth — сколько поколений вверх показывать.
    - F — уже посчитанные F (нужны, чтобы подсветить инбредных предков).

    Возвращает строку в синтаксисе Graphviz DOT, которую Streamlit
    превращает в SVG-граф через st.graphviz_chart.
    """
    edges: set[tuple[str, str]] = set()    
    visited: set[str] = set()              

    def walk(node: str, d: int) -> None:
        
        if d == 0 or node in visited:
            return
        visited.add(node)
        for parent in ped.parents(node):
            if parent is None:
                continue
            
            edges.add((parent, node))
            walk(parent, d - 1)

    walk(root, depth)

    
    
    
    lines = ["digraph G {", "  rankdir=BT;", "  node [shape=box, style=rounded];"]
    for node in visited:
        Fv = F.get(node, 0.0)
        
        color = "lightcoral" if Fv > 1e-9 else "white"
        label = f"{node}\\nF={Fv:.4f}" if Fv > 1e-9 else node
        lines.append(
            f'  "{node}" [label="{label}", fillcolor="{color}", style="filled,rounded"];'
        )
    for parent, child in edges:
        lines.append(f'  "{parent}" -> "{child}";')
    lines.append("}")
    return "\n".join(lines)








st.set_page_config(page_title="Калькулятор инбридинга", layout="wide")

st.title("Калькулятор инбридинга и родства (метод Райта / Хендерсона)")
st.caption(
    "Загрузите родословную (CSV/XLSX) или используйте пример. "
    "Программа считает коэффициент инбридинга F для всех особей и "
    "коэффициент родства R между любой парой."
)






with st.expander("1. Загрузка родословной", expanded=True):
    
    col_a, col_b, col_c = st.columns([2, 1, 1])

    with col_a:
        uploaded = st.file_uploader(
            "Файл с родословной",
            type=["csv", "xlsx", "xls"],
            help=(
                "Колонки: id, father, mother. Допустимы алиасы: "
                "animal/sire/dam, кличка/отец/мать."
            ),
        )

    with col_b:
        use_example = st.button("Загрузить пример (7 особей)")

    with col_c:
        gen_synthetic = st.button("Сгенерировать 1000 особей")

    
    
    if "df" not in st.session_state:
        st.session_state.df = None

    if uploaded is not None:
        try:
            if uploaded.name.endswith(".csv"):
                st.session_state.df = pd.read_csv(uploaded)
            else:
                st.session_state.df = pd.read_excel(uploaded)
        except Exception as e:
            st.error(f"Не удалось прочитать файл: {e}")

    if use_example:
        
        st.session_state.df = pd.DataFrame(
            [
                {"id": "A", "father": "", "mother": ""},
                {"id": "B", "father": "", "mother": ""},
                {"id": "C", "father": "A", "mother": "B"},
                {"id": "D", "father": "A", "mother": "B"},
                {"id": "E", "father": "C", "mother": "D"},
                {"id": "F", "father": "E", "mother": "D"},
                {"id": "G", "father": "F", "mother": "D"},
            ]
        )

    if gen_synthetic:
        
        st.session_state.df = generate_pedigree(20, 8, 125)

    df = st.session_state.df

    if df is not None:
        st.write(f"Загружено строк: **{len(df)}**")
        st.dataframe(df.head(50), use_container_width=True)








if st.session_state.df is None:
    st.info("Загрузите файл или используйте пример выше, чтобы продолжить.")
    st.stop()


with st.expander("2. Валидация", expanded=True):
    try:
        
        
        ped = load_dataframe(st.session_state.df)
        st.success(
            f"Родословная корректна. Особей: {len(ped)}, основателей: {len(ped.founders())}"
        )
        
        st.session_state.ped = ped
    except (PedigreeError, ValueError) as e:
        st.error(f"Ошибка в данных: {e}")
        st.stop()


ped: Pedigree = st.session_state.ped






with st.expander("3. Коэффициент инбридинга F", expanded=True):
    
    
    if "F" not in st.session_state or st.session_state.get("F_for") != id(ped):
        with st.spinner("Считаю матрицу родства..."):
            compute_relationship_matrix(ped)
            st.session_state.F = compute_inbreeding(ped)
            st.session_state.F_for = id(ped)

    F: dict[str, float] = st.session_state.F

    
    rows = []
    for ind in ped.order:
        f, m = ped.parents(ind)
        Fv = F[ind]
        rows.append(
            {
                "id": ind,
                "father": f or "",
                "mother": m or "",
                "F": round(Fv, 6),
                "type": classify_inbreeding(Fv).name if Fv > 1e-9 else "—",
            }
        )
    
    df_F = pd.DataFrame(rows).sort_values("F", ascending=False).reset_index(drop=True)

    
    n_inbred = int((df_F["F"] > 1e-9).sum())
    max_F = float(df_F["F"].max() or 0)

    cc1, cc2, cc3 = st.columns(3)
    cc1.metric("Всего особей", len(df_F))
    cc2.metric("Инбредных (F>0)", n_inbred)
    cc3.metric("Максимальный F", f"{max_F:.4f}")

    
    st.dataframe(df_F, use_container_width=True, height=350)

    
    csv_bytes = df_F.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Скачать результат CSV", csv_bytes, "inbreeding.csv", "text/csv"
    )






with st.expander("4. Детальный анализ пробанда (метод Райта)", expanded=False):
    
    
    proband = st.selectbox(
        "Выберите пробанда", options=ped.ids(), index=len(ped.ids()) - 1
    )

    Fp = F[proband]
    mt = classify_inbreeding(Fp)
    cc1, cc2 = st.columns([1, 2])
    cc1.metric(f"F пробанда {proband}", f"{Fp:.6f}")
    cc2.markdown(f"**Тип спаривания:** {mt.name} (эталон F={mt.F})")

    
    if Fp > 1e-9:
        
        
        if len(ped) > 200:
            st.warning(
                "Метод Райта с разложением путей включён только для родословных "
                "до 200 особей (на больших долго). Используется табличный F."
            )
        else:
            with st.spinner("Перечисляю пути..."):
                wF, contribs = wright_paths(ped, proband, F)

            st.write(
                f"Сумма по путям: **{wF:.6f}** (должна совпадать с табличным F)."
            )

            if contribs:
                
                
                ctab = pd.DataFrame(
                    [
                        {
                            "ancestor": c.ancestor,
                            "n1 (отец→предок)": c.n1,
                            "n2 (мать→предок)": c.n2,
                            "F(предка)": round(c.ancestor_F, 6),
                            "вклад": round(c.contribution, 6),
                            "путь отца": " → ".join(c.sire_path),
                            "путь матери": " → ".join(c.dam_path),
                        }
                        for c in contribs
                    ]
                )
                st.dataframe(ctab, use_container_width=True)

    
    if st.checkbox("Показать графовую визуализацию родословной пробанда"):
        depth = st.slider("Глубина (поколений)", 1, 8, 4)
        st.graphviz_chart(build_dot(ped, proband, depth, F))






with st.expander("5. Родство пары особей", expanded=False):
    cc1, cc2 = st.columns(2)
    with cc1:
        x = st.selectbox("Особь X", options=ped.ids(), key="pair_x")
    with cc2:
        
        
        y = st.selectbox(
            "Особь Y",
            options=ped.ids(),
            key="pair_y",
            index=min(1, len(ped.ids()) - 1),
        )

    if x and y:
        f_xy = kinship(ped, x, y)
        r_xy = relationship(ped, x, y)
        cc1, cc2 = st.columns(2)
        cc1.metric("Коанцестрия f(X,Y)", f"{f_xy:.6f}")
        cc2.metric("Родство R(X,Y)", f"{r_xy:.6f}")

        
        
        if x != y:
            mt = classify_inbreeding(f_xy)
            st.info(
                f"Если скрестить **{x}** и **{y}**, потомок будет иметь F ≈ "
                f"**{f_xy:.4f}** ({mt.name})."
            )


st.caption(
    "Алгоритм: метод Хендерсона (tabular) для матрицы родства A; "
    "F(i)=A(i,i)−1; R=2·A[i,j]/√((1+F(i))(1+F(j))). "
    "Метод Райта используется только для образовательного разложения по путям."
)
