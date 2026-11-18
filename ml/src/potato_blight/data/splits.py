"""Particiones estratificadas por grupo e invariantes contra fuga de información."""

from itertools import combinations

import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from potato_blight import CLASSES


class LeakageError(ValueError):
    """Hay imágenes o grupos compartidos entre particiones."""


def assign_folds(df: pd.DataFrame, train_datasets: list[str], n_splits: int = 5, seed: int = 2026) -> pd.DataFrame:
    if n_splits < 3:
        raise ValueError("Se requieren al menos 3 particiones para entrenamiento, validación y prueba.")
    result = df.copy()
    result["fold"] = -1
    train = result[result["dataset_id"].isin(train_datasets)]
    counts = train.groupby("label")["group_id"].nunique().reindex(CLASSES, fill_value=0)
    if (counts < n_splits).any():
        raise ValueError(f"No hay suficientes grupos por clase para {n_splits} folds: {counts.to_dict()}")
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    for fold, (_, indices) in enumerate(splitter.split(train, train["label"], train["group_id"])):
        result.loc[train.index[indices], "fold"] = fold
    for fold in range(n_splits):
        if set(result[result["fold"] == fold]["label"]) != set(CLASSES):
            raise ValueError(f"El fold {fold} no contiene todas las clases; revise grupos o reduzca n_splits.")
    return result


def fold_split(df: pd.DataFrame, fold: int, n_splits: int) -> dict[str, pd.DataFrame]:
    if not 0 <= fold < n_splits:
        raise ValueError("Fold fuera de rango")
    cv = df[df["fold"] >= 0]
    val = (fold + 1) % n_splits
    return {"train": cv[~cv["fold"].isin([fold, val])].copy(), "val": cv[cv["fold"] == val].copy(),
            "test": cv[cv["fold"] == fold].copy()}


def external_split(df: pd.DataFrame, external_datasets: list[str], train_datasets: list[str]) -> pd.DataFrame:
    groups = set(df[df["dataset_id"].isin(train_datasets)]["group_id"])
    return df[df["dataset_id"].isin(external_datasets) & ~df["group_id"].isin(groups)].copy()


def check_no_leakage(parts: dict[str, pd.DataFrame]) -> None:
    for (a, left), (b, right) in combinations(parts.items(), 2):
        for column in ("group_id", "sha256"):
            if column in left and column in right and set(left[column].dropna()) & set(right[column].dropna()):
                raise LeakageError(f"{column} compartido entre {a} y {b}")
        if all(c in left and c in right for c in ("dataset_id", "path")):
            first = set(zip(left["dataset_id"], left["path"], strict=True))
            second = set(zip(right["dataset_id"], right["path"], strict=True))
            if first & second:
                raise LeakageError(f"Misma imagen en {a} y {b}")
