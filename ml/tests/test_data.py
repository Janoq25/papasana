import pandas as pd
import pytest
from PIL import Image

from potato_blight.data.dedup import assign_groups, near_duplicate_pairs
from potato_blight.data.imagehash import dhash, hamming
from potato_blight.data.index import build_manifest
from potato_blight.data.registry import DatasetEntry, LicenseNotVerified, load_registry
from potato_blight.data.splits import LeakageError, assign_folds, check_no_leakage, external_split, fold_split
from potato_blight.data.synthetic import generate


def test_registro_valido_y_sin_licencias_inventadas():
    reg = load_registry()
    pv = reg.get("plantvillage_papa")
    # Early blight (Alternaria) NUNCA se mapea a tizón tardío (D-01)
    assert pv.class_map["Potato___Early_blight"] == "otra_enfermedad_foliar"
    assert pv.class_map["Potato___Late_blight"] == "sintomas_compatibles_tizon_tardio"
    # La verificación se respalda en la fuente oficial fijada, no en copias de terceros.
    for ds in ("plantvillage_papa", "plantdoc_papa"):
        entry = reg.get(ds)
        assert entry.usable and entry.license_url.startswith("https://github.com/")
        assert entry.version in entry.license_url
    assert pv.has_group_ids
    assert reg.get("sintetico_smoke").usable


def test_clase_desconocida_en_el_registro():
    with pytest.raises(ValueError):
        DatasetEntry(id="x", name="x", conditions="campo", role="entrenamiento", class_map={"a": "tizon"})


def test_no_se_indexa_un_dataset_sin_licencia(tmp_path):
    entry = load_registry().get("plantvillage_papa")
    entry = entry.model_copy(update={"license_status": "por_verificar"})
    with pytest.raises(LicenseNotVerified):
        build_manifest(entry, tmp_path)


def test_dhash_igual_al_del_backend():
    # Misma implementación que backend/app/domain/images.py (con signo allí; aquí sin signo)
    img = Image.new("L", (90, 80))
    img.putdata([(x * 3 + y) % 256 for y in range(80) for x in range(90)])
    h = dhash(img)
    small = img.resize((9, 8), Image.Resampling.LANCZOS)
    px = [small.getpixel((c, r)) for r in range(8) for c in range(9)]
    bits = 0
    for r in range(8):
        for c in range(8):
            bits = (bits << 1) | (1 if px[r * 9 + c] > px[r * 9 + c + 1] else 0)
    assert h == bits


def test_pares_casi_duplicados_sin_falsos_negativos():
    import random

    rng = random.Random(1)
    hashes = [rng.getrandbits(64) for _ in range(300)]
    hashes.append(hashes[10] ^ 0b101)          # distancia 2 de la imagen 10
    hashes.append(hashes[20] ^ (0b1111 << 30))  # distancia 4 de la 20
    found = near_duplicate_pairs(hashes, 4)
    brute = {(i, j) for i in range(len(hashes)) for j in range(i + 1, len(hashes))
             if hamming(hashes[i], hashes[j]) <= 4}
    assert found == brute and (10, 300) in found and (20, 301) in found


def _df(rows):
    return pd.DataFrame(rows, columns=["path", "dataset_id", "source_label", "label", "sha256", "dhash", "width",
                                       "height", "source_group"])


def test_grupos_deduplicacion_y_compartidos_entre_datasets():
    rows = [
        ["a.png", "pv", "x", "sano", "s1", 0, 1, 1, None],
        ["a_copia.png", "pv", "x", "sano", "s1", 0, 1, 1, None],          # duplicado exacto
        ["b.png", "pv", "x", "sano", "s2", 0b111, 1, 1, None],            # casi duplicado de a
        ["c.png", "pv", "x", "sano", "s3", (1 << 63) - 1, 1, 1, "planta7"],
        ["d.png", "pv", "x", "sano", "s4", 123456789, 1, 1, "planta7"],   # misma planta que c
        ["e.png", "pd", "x", "sano", "s5", 0b11, 1, 1, None],             # copia de PlantVillage en PlantDoc
    ]
    out = assign_groups(_df(rows), max_distance=4)
    assert len(out) == 5  # se elimina la copia exacta
    g = dict(zip(out["path"], out["group_id"], strict=True))
    assert g["a.png"] == g["b.png"] == g["e.png"]
    assert g["c.png"] == g["d.png"] != g["a.png"]
    assert bool(out.set_index("path").loc["e.png", "cross_dataset"])
    ext = external_split(out.assign(fold=-1), ["pd"], ["pv"])
    assert ext.empty  # la imagen compartida no cuenta como validación externa


def test_particiones_agrupadas_sin_fuga(tmp_path):
    root = generate(tmp_path / "img", plants_per_class=6, views_per_plant=3, size=48)
    entry = load_registry().get("sintetico_smoke")
    df = assign_groups(build_manifest(entry, root))
    assert len(df) == 3 * 6 * 3
    df = assign_folds(df, ["sintetico_smoke"], n_splits=3)
    assert (df["fold"] >= 0).all()
    # Cada planta (grupo de la fuente) queda en una sola partición
    assert (df.groupby("source_group")["fold"].nunique() == 1).all()
    for k in range(3):
        parts = fold_split(df, k, 3)
        check_no_leakage(parts)
        assert set(parts["test"]["label"]) == {"sano", "sintomas_compatibles_tizon_tardio", "otra_enfermedad_foliar"}
    bad = {"train": df.iloc[:2], "test": df.iloc[1:3]}
    with pytest.raises(LeakageError):
        check_no_leakage(bad)
