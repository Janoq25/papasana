"""Fase 4: laboratorio de modelos (sincronización, detalle, comparación, promoción y rollback con cuatro ojos)
y registro de datasets y licencias (A1). MLflow y ml-service se simulan en memoria."""

import json

import pytest
import yaml
from sqlalchemy import select

from app.core.errors import PermissionDeniedError, ServiceUnavailableError
from app.main import app
from app.models import AuditLog, ModelPromotion, ModelVersion, Notification, User
from app.services.lab_service import LabService
from app.services.ml_client import get_ml_client
from app.services.mlflow_client import get_mlflow_client
from tests.conftest import DEMO, login

L = "/api/v1/laboratorio"
DEMO_KEY = "demo-resnet50-imagenet-v1"


class FakeMLflow:
    """Registro de modelos en memoria con la misma interfaz que MLflowClient."""

    configured = True

    def __init__(self):
        self.models: dict[str, dict[str, dict]] = {}
        self.aliases: dict[str, str] = {}
        self.runs: dict[str, dict] = {}
        self.artifacts: dict[tuple[str, str], dict] = {}
        self.comparisons: list[dict] = []

    def add_version(self, arch: str, version: str, *, smoke=False, metrics=None):
        name = f"papasana-{arch.replace('_', '-')}"
        run_id = f"run-{arch}-{version}"
        metrics = metrics or {"val_macro_f1": 0.8, "val_accuracy": 0.82}
        self.models.setdefault(name, {})[version] = {
            "name": name, "version": version, "run_id": run_id, "creation_timestamp": 1794500000000,
            "tags": [{"key": "architecture", "value": arch}, {"key": "smoke_test", "value": str(smoke).lower()},
                     {"key": "temperature", "value": "1.25"}, {"key": "dataset_ids", "value": "plantvillage_papa"},
                     {"key": "metrics_summary", "value": json.dumps(metrics)}]}
        self.runs[run_id] = {"info": {"run_id": run_id, "experiment_id": "1"}, "metrics": metrics,
                             "params": {"architecture": arch}, "tags": {"run_type": "final"}}
        self.artifacts[(run_id, "evaluation.json")] = {"val": {"macro_f1": metrics.get("val_macro_f1"),
                                                               "confusion_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}}
        return name

    def health(self):
        return True

    def registered_models(self):
        return [{"name": n, "aliases": ([{"alias": "production", "version": self.aliases[n]}]
                                        if n in self.aliases else [])} for n in self.models]

    def model_versions(self, name):
        return list(self.models.get(name, {}).values())

    def set_alias(self, name, version, alias="production"):
        self.aliases[name] = str(version)

    def delete_alias(self, name, alias="production"):
        self.aliases.pop(name, None)

    def alias_holders(self, alias="production"):
        return list(self.aliases.items())

    def get_run(self, run_id):
        return self.runs.get(run_id)

    def metric_history(self, run_id, key):
        return [{"step": 1, "value": 1.0}, {"step": 2, "value": 0.5}] if run_id in self.runs else []

    def artifact_json(self, run_id, path):
        if path == "comparison.json":
            return next((c["data"] for c in self.comparisons if c["run_id"] == run_id), None)
        return self.artifacts.get((run_id, path))

    def search_runs(self, experiment, filter_string, max_results=20):
        return [{"info": {"run_id": c["run_id"], "start_time": 1},
                 "data": {"tags": [{"key": "smoke_test", "value": str(c["smoke"]).lower()}]}} for c in self.comparisons]


class FakeServing:
    """ml-service simulado: al recargar sirve la versión con alias production (o el DEMO)."""

    def __init__(self, registry: FakeMLflow):
        self.registry = registry
        self.fail = False
        self.reloads = 0

    def model_info(self):
        holders = self.registry.alias_holders()
        return {"key": f"{holders[0][0]}:v{holders[0][1]}" if holders else DEMO_KEY}

    def reload(self):
        self.reloads += 1
        if self.fail:
            raise ServiceUnavailableError("ml-service no pudo cargar el modelo: descarga interrumpida")
        return self.model_info()


@pytest.fixture
def registry():
    return FakeMLflow()


@pytest.fixture
def serving(registry):
    return FakeServing(registry)


@pytest.fixture
def lab_client(client, registry, serving):
    app.dependency_overrides[get_mlflow_client] = lambda: registry
    app.dependency_overrides[get_ml_client] = lambda: serving
    return client


def _user(db, role):
    return db.scalar(select(User).where(User.email == DEMO[role]))


def _model(db, key):
    return db.scalar(select(ModelVersion).where(ModelVersion.model_key == key))


def _synced(lab_client, registry, *versions):
    for arch, version, smoke in versions:
        registry.add_version(arch, version, smoke=smoke)
    r = lab_client.post(f"{L}/sincronizar", headers=login(lab_client, "INVESTIGADOR"))
    assert r.status_code == 200, r.text
    return r.json()


# --- Sincronización y consulta -----------------------------------------------------------------------

def test_sincronizacion_con_el_registro(lab_client, db, registry):
    registry.add_version("convnext_tiny", "1")
    registry.set_alias("papasana-convnext-tiny", "1")  # alias puesto fuera de la aplicación
    out = _synced(lab_client, registry, ("resnet50", "1", True))
    assert out["creados"] == 2 and out["en_produccion"] == ["papasana-convnext-tiny:v1"]
    smoke = _model(db, "papasana-resnet50:v1")
    assert smoke.is_demo and smoke.smoke_test and smoke.stage == "staging"
    assert smoke.display_name.startswith("SMOKE TEST / no validado") and smoke.temperature == 1.25
    assert smoke.train_dataset_ids == ["plantvillage_papa"] and smoke.metrics_summary["val_macro_f1"] == 0.8
    assert _model(db, "papasana-convnext-tiny:v1").stage == "production"
    lista = lab_client.get(f"{L}/modelos", headers=login(lab_client, "AGRONOMO")).json()
    assert lista[0]["model_key"] == "papasana-convnext-tiny:v1"  # producción primero
    assert DEMO_KEY in [m["model_key"] for m in lista]
    ev = db.scalar(select(AuditLog).where(AuditLog.action == "sincronizar"))
    assert ev is not None and ev.module_code == "laboratorio"


def test_detalle_y_comparacion_sin_inventar_metricas(lab_client, db, registry):
    _synced(lab_client, registry, ("cnn_vit", "1", False))
    inv = login(lab_client, "INVESTIGADOR")
    demo = lab_client.get(f"{L}/modelos/{_model(db, DEMO_KEY).id}", headers=inv).json()
    assert demo["run"] is None and "D-16" in demo["mensaje"]
    det = lab_client.get(f"{L}/modelos/{_model(db, 'papasana-cnn-vit:v1').id}", headers=inv).json()
    assert det["run"]["metrics"]["val_macro_f1"] == 0.8 and det["evaluacion"]["val"]["confusion_matrix"]
    assert det["historial"]["val_loss"][1]["value"] == 0.5 and "#/experiments/1/runs/" in det["mlflow_url"]
    assert lab_client.get(f"{L}/comparacion", headers=inv).json()["estado"] == "sin_experimentos"
    registry.comparisons.append({"run_id": "cmp-smoke", "smoke": True, "data": {"estado": "ok", "modelos": ["x"]}})
    c = lab_client.get(f"{L}/comparacion", headers=inv).json()
    assert c["estado"] == "ok" and c["solo_prueba_de_humo"] is True


# --- Promoción con cuatro ojos ----------------------------------------------------------------------------

def test_promocion_con_cuatro_ojos_cambia_el_modelo_en_uso(lab_client, db, registry, serving):
    _synced(lab_client, registry, ("resnet50", "1", True))
    target = _model(db, "papasana-resnet50:v1")
    inv, adm = login(lab_client, "INVESTIGADOR"), login(lab_client, "ADMINISTRADOR")
    body = {"model_version_id": target.id, "action": "promover", "reason": "Prueba de humo de la Fase 4"}
    # El administrador no solicita (no tiene laboratorio:crear) y el investigador no aprueba
    assert lab_client.post(f"{L}/promociones", headers=adm, json=body).status_code == 403
    r = lab_client.post(f"{L}/promociones", headers=inv, json=body)
    assert r.status_code == 201 and r.json()["status"] == "pendiente"
    pid = r.json()["id"]
    assert lab_client.post(f"{L}/promociones", headers=inv, json=body).status_code == 409  # ya hay una pendiente
    assert lab_client.post(f"{L}/promociones/{pid}/aprobar", headers=inv, json={}).status_code == 403
    aviso = db.scalar(select(Notification).where(Notification.kind == "aprobacion_modelo"))
    assert aviso is not None and aviso.user_id == _user(db, "ADMINISTRADOR").id

    r = lab_client.post(f"{L}/promociones/{pid}/aprobar", headers=adm, json={"reason": "Revisado"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "aplicada" and out["requested_by_name"] == "Iván Investigador"
    assert out["decided_by_name"] == "Ana Administradora"
    assert registry.aliases == {"papasana-resnet50": "1"} and serving.reloads == 1
    db.refresh(target)
    assert target.stage == "production"
    events = db.scalars(select(AuditLog).where(AuditLog.entity_type == "promocion_modelo")).all()
    assert {e.action for e in events} >= {"crear", "aprobar"}
    aprob = next(e for e in events if e.action == "aprobar" and e.result == "exito")
    assert aprob.before == {"en_uso": "demo"} and aprob.after["en_uso"] == "papasana-resnet50:v1"


def test_el_solicitante_no_aprueba_su_propia_solicitud(db, registry, serving):
    registry.add_version("resnet50", "1")
    svc = LabService(db, registry, serving)
    svc.sync()
    admin = _user(db, "ADMINISTRADOR")
    promo = svc.request(admin, None, _model(db, "papasana-resnet50:v1").id, "promover", "Solicitud del mismo usuario")
    with pytest.raises(PermissionDeniedError) as e:
        svc.approve(admin, None, promo.id, None)
    assert e.value.code == "cuatro_ojos" and registry.aliases == {}
    assert db.scalar(select(AuditLog).where(AuditLog.error_detail.like("cuatro ojos%"))) is not None


def test_recarga_fallida_revierte_el_alias(lab_client, db, registry, serving):
    _synced(lab_client, registry, ("resnet50", "1", False), ("resnet50", "2", False))
    registry.set_alias("papasana-resnet50", "1")
    svc = LabService(db, registry, serving)
    svc.sync()
    promo = svc.request(_user(db, "INVESTIGADOR"), None, _model(db, "papasana-resnet50:v2").id, "promover",
                        "Versión con mejor validación externa")
    serving.fail = True
    with pytest.raises(ServiceUnavailableError):
        svc.approve(_user(db, "ADMINISTRADOR"), None, promo.id, "ok")
    db.refresh(promo)
    assert promo.status == "fallida" and "descarga" in promo.error
    assert registry.aliases == {"papasana-resnet50": "1"}  # el alias volvió a la versión anterior
    assert _model(db, "papasana-resnet50:v1").stage == "production"


def test_rollback_a_la_version_anterior_y_al_demo(db, registry, serving):
    registry.add_version("resnet50", "1")
    registry.add_version("efficientnet_b3", "1")
    svc = LabService(db, registry, serving)
    svc.sync()
    inv, adm = _user(db, "INVESTIGADOR"), _user(db, "ADMINISTRADOR")
    v1, eff = _model(db, "papasana-resnet50:v1"), _model(db, "papasana-efficientnet-b3:v1")
    svc.approve(adm, None, svc.request(inv, None, v1.id, "promover", "Primera versión entrenada").id, None)
    svc.approve(adm, None, svc.request(inv, None, eff.id, "promover", "Mejor en validación cruzada").id, None)
    assert registry.aliases == {"papasana-efficientnet-b3": "1"}  # un solo modelo con el alias
    db.refresh(v1)
    assert v1.stage == "archived"
    # Rollback a una versión que nunca estuvo en producción: no se permite
    registry.add_version("convnext_tiny", "1")
    svc.sync()
    with pytest.raises(Exception, match="estuvo en producción"):
        svc.request(inv, None, _model(db, "papasana-convnext-tiny:v1").id, "rollback", "No corresponde hacerlo")
    rb = svc.request(inv, None, v1.id, "rollback", "La nueva versión falla en campo")
    svc.approve(adm, None, rb.id, "Confirmado")
    assert registry.aliases == {"papasana-resnet50": "1"}
    db.refresh(eff)
    assert eff.stage == "archived"
    demo = svc.request(inv, None, _model(db, DEMO_KEY).id, "rollback", "Retirar el modelo entrenado")
    svc.approve(adm, None, demo.id, None)
    assert registry.aliases == {} and svc.current_production() is None
    historial = db.scalars(select(ModelPromotion).where(ModelPromotion.status == "aplicada")).all()
    assert len(historial) == 4


def test_rechazo_y_cancelacion(lab_client, db, registry):
    _synced(lab_client, registry, ("resnet50", "1", False))
    inv, adm = login(lab_client, "INVESTIGADOR"), login(lab_client, "ADMINISTRADOR")
    mid = _model(db, "papasana-resnet50:v1").id
    pid = lab_client.post(f"{L}/promociones", headers=inv, json={"model_version_id": mid, "action": "promover",
                                                                 "reason": "Candidata a producción"}).json()["id"]
    assert lab_client.post(f"{L}/promociones/{pid}/rechazar", headers=adm, json={}).status_code == 422
    r = lab_client.post(f"{L}/promociones/{pid}/rechazar", headers=adm, json={"reason": "Falta validación externa"})
    assert r.json()["status"] == "rechazada"
    segundo = {"model_version_id": mid, "action": "promover", "reason": "Segundo intento con más datos"}
    pid = lab_client.post(f"{L}/promociones", headers=inv, json=segundo).json()["id"]
    r = lab_client.post(f"{L}/promociones/{pid}/rechazar", headers=inv, json={"reason": "Me equivoqué"})
    assert r.json()["status"] == "cancelada"
    assert len(lab_client.get(f"{L}/promociones", headers=adm).json()) == 2


def test_kpi_de_precision_solo_con_modelo_real_en_produccion(lab_client, db, registry, serving):
    registry.add_version("resnet50", "1", metrics={"cv_mean_test_accuracy": 0.91, "val_accuracy": 0.9})
    svc = LabService(db, registry, serving)
    svc.sync()
    mv = _model(db, "papasana-resnet50:v1")
    svc.approve(_user(db, "ADMINISTRADOR"), None,
                svc.request(_user(db, "INVESTIGADOR"), None, mv.id, "promover", "Modelo validado").id, None)
    k = lab_client.get("/api/v1/dashboard", headers=login(lab_client, "ADMINISTRADOR")).json()["kpis"]
    assert k["precision_modelo"]["valor"] == 0.91 and "cruzada" in k["precision_modelo"]["fuente"]
    mv.smoke_test = True
    db.commit()
    k = lab_client.get("/api/v1/dashboard", headers=login(lab_client, "ADMINISTRADOR")).json()["kpis"]
    assert k["precision_modelo"]["valor"] is None and "humo" in k["precision_modelo"]["motivo"]


# --- Datasets y licencias (A1) ----------------------------------------------------------------------------

def test_registro_de_datasets_y_verificacion_de_licencia(client, db):
    inv = login(client, "INVESTIGADOR")
    lista = {d["code"]: d for d in client.get("/api/v1/datasets", headers=inv).json()}
    assert set(lista) == {"plantvillage_papa", "plantdoc_papa", "app_validadas", "sintetico_smoke"}
    assert lista["plantvillage_papa"]["license_status"] == "por_verificar" and not lista["plantvillage_papa"]["usable"]
    assert lista["plantvillage_papa"]["license"] is None  # no se inventa la licencia
    pid = lista["plantdoc_papa"]["id"]
    # Verificar exige licencia, enlace a la fuente y la descripción de la revisión
    r = client.put(f"/api/v1/datasets/{pid}/licencia", headers=inv, json={"license_status": "verificada"})
    assert r.status_code == 422 and r.json()["code"] == "licencia_incompleta"
    r = client.put(f"/api/v1/datasets/{pid}/licencia", headers=inv, json={
        "license_status": "verificada", "license": "CC BY 4.0",
        "license_url": "https://github.com/pratikkayal/PlantDoc-Dataset", "license_notes": "Revisado el LICENSE"})
    assert r.status_code == 200 and r.json()["usable"] and r.json()["license_verified_by_name"] == "Iván Investigador"
    ev = db.scalar(select(AuditLog).where(AuditLog.action == "verificar_licencia"))
    assert ev.before["license_status"] == "por_verificar" and ev.after["license_status"] == "verificada"
    # Exportación en el formato de ml/datasets.yaml
    r = client.get("/api/v1/datasets/exportar", headers=inv)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = yaml.safe_load(r.text)
    pd_ = next(d for d in data["datasets"] if d["id"] == "plantdoc_papa")
    assert pd_["license_status"] == "verificada" and pd_["license_verified_by"].startswith("Iván Investigador")
    assert next(d for d in data["datasets"] if d["id"] == "plantvillage_papa")["license_verified_by"] is None


def test_crear_editar_y_borrar_datasets(client, db):
    inv, adm = login(client, "INVESTIGADOR"), login(client, "ADMINISTRADOR")
    body = {"code": "campo_junin_2026", "name": "Fotos de campo Junín 2026", "conditions": "campo",
            "role": "validacion_externa", "class_map": {"sana": "sano", "tizon": "sintomas_compatibles_tizon_tardio"}}
    r = client.post("/api/v1/datasets", headers=inv, json=body)
    assert r.status_code == 201 and r.json()["license_status"] == "por_verificar"
    did = r.json()["id"]
    assert client.post("/api/v1/datasets", headers=inv, json=body).status_code == 409
    bad = {**body, "code": "otro_dataset", "class_map": {"x": "tizon"}}
    assert client.post("/api/v1/datasets", headers=inv, json=bad).status_code == 422
    assert client.patch(f"/api/v1/datasets/{did}", headers=inv, json={"n_images": 120}).json()["n_images"] == 120
    assert client.delete(f"/api/v1/datasets/{did}", headers=inv).status_code == 403  # el investigador no elimina
    assert client.get("/api/v1/datasets", headers=login(client, "TECNICO")).status_code == 403
    db.add(ModelVersion(model_key="papasana-x:v1", architecture="resnet50", display_name="x", classes=[],
                        train_dataset_ids=["campo_junin_2026"], source="mlflow"))
    db.commit()
    assert client.delete(f"/api/v1/datasets/{did}", headers=adm).status_code == 409  # lo usa un modelo
