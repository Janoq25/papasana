import pytest

from potato_blight.download_public import potato_leaf_group


def test_id_de_hoja_se_filtra_por_cultivo_y_clase():
    source = {"rs_hl 1830": ["Potato___healthy:::12.0", "Strawberry___healthy:::22.0"]}
    assert potato_leaf_group(source, "Potato___healthy/uuid___RS_HL 1830.JPG") == "Potato___healthy:::12.0"


def test_id_ausente_o_ambiguo_no_se_inventa():
    with pytest.raises(ValueError, match="ausente o ambiguo"):
        potato_leaf_group({"rs_hl 1830": ["Strawberry___healthy:::22.0"]},
                          "Potato___healthy/uuid___RS_HL 1830.JPG")
