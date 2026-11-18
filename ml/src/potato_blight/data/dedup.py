"""Agrupa IDs publicados y duplicados exactos/perceptuales dentro y entre fuentes."""

import hashlib

import pandas as pd

from potato_blight.data.imagehash import hamming


def near_duplicate_pairs(hashes: list[int], max_distance: int = 4) -> set[tuple[int, int]]:
    return {(i, j) for i, first in enumerate(hashes) for j in range(i + 1, len(hashes))
            if hamming(first, hashes[j]) <= max_distance}


def assign_groups(df: pd.DataFrame, max_distance: int = 4) -> pd.DataFrame:
    df = df.reset_index(drop=True).copy()
    parents = list(range(len(df)))

    def find(i: int) -> int:
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    def union(i: int, j: int) -> None:
        a, b = find(i), find(j)
        if a != b:
            parents[max(a, b)] = min(a, b)

    for columns in (["sha256"], ["dataset_id", "source_group"]):
        valid = df.dropna(subset=columns)
        for indices in valid.groupby(columns, sort=True).groups.values():
            indices = list(indices)
            for i in indices[1:]:
                union(indices[0], i)
    for i, j in near_duplicate_pairs([int(v) for v in df["dhash"]], max_distance):
        union(i, j)
    roots = [find(i) for i in range(len(df))]
    canonical = {}
    for root, rows in df.groupby(pd.Series(roots)):
        signature = "\n".join(sorted(rows["dataset_id"] + ":" + rows["path"]))
        canonical[root] = "g-" + hashlib.sha256(signature.encode()).hexdigest()[:20]
    df["group_id"] = [canonical[r] for r in roots]
    # Se calculan ANTES de retirar copias: una copia exacta externa no vuelve independiente al grupo.
    df["cross_dataset"] = df.groupby("group_id")["dataset_id"].transform("nunique") > 1
    df["label_conflict"] = df.groupby("group_id")["label"].transform("nunique") > 1
    return df.drop_duplicates("sha256", keep="first").reset_index(drop=True)


def dedup_report(raw: pd.DataFrame, grouped: pd.DataFrame) -> dict:
    return {"imagenes_originales": len(raw), "imagenes_sin_duplicados_exactos": len(grouped),
            "duplicados_exactos_eliminados": len(raw) - len(grouped),
            "grupos": int(grouped["group_id"].nunique()),
            "imagenes_en_grupos_compartidos": int(grouped["cross_dataset"].sum()),
            "imagenes_con_etiquetas_en_conflicto": int(grouped["label_conflict"].sum())}
