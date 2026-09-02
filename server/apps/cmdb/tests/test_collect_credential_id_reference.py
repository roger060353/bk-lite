import pytest

from apps.cmdb.models.collect_model import CollectModels
from apps.cmdb.services.collect_credential_reference import stored_credential_has_secret_blob
from apps.system_mgmt.models import ConnectionCredential
from apps.system_mgmt.services.connection_credential_service import ConnectionCredentialService

pytestmark = pytest.mark.django_db


def _create_task(**overrides):
    values = {
        "name": "cred-ref-task",
        "task_type": "host",
        "driver_type": "job",
        "model_id": "host",
        "cycle_value_type": "cycle",
        "team": [1],
        "credential": [{"username": "admin", "password": "nested-secret", "port": 22}],
    }
    values.update(overrides)
    task = CollectModels.objects.create(**values)
    task.refresh_from_db()
    return task


def test_new_save_never_persists_password():
    task = _create_task()
    stored = task.credential[0]
    assert stored.get("system_credential_id")
    assert stored.get("password") in (None, "")
    assert stored.get("username") in (None, "")
    assert stored_credential_has_secret_blob(task.credential, model_id="host", driver_type="job") is False
    assert "nested-secret" not in str(task.credential)
    assert ConnectionCredential.objects.filter(pk=int(stored["system_credential_id"])).exists()


def test_old_nested_password_still_decrypts_without_resave():
    task = CollectModels(
        name="legacy-unsaved",
        task_type="host",
        driver_type="job",
        model_id="host",
        cycle_value_type="cycle",
        credential=[{"credential_id": "cred-1", "username": "admin", "password": CollectModels.encrypt_password("legacy-plain")}],
    )
    decrypted = task.decrypt_credentials
    assert decrypted[0]["password"] == "legacy-plain"
    assert decrypted[0]["username"] == "admin"
    assert decrypted[0]["credential_id"] == "cred-1"


def test_resave_strips_nested_password_and_writes_id():
    task = CollectModels(
        name="legacy-resave",
        task_type="host",
        driver_type="job",
        model_id="host",
        cycle_value_type="cycle",
        team=[1],
    )
    task.credential = [{"credential_id": "cred-legacy", "username": "ops", "password": CollectModels.encrypt_password("keep-reading")}]
    CollectModels.objects.bulk_create([task])
    task = CollectModels.objects.get(name="legacy-resave")
    assert task.credential[0]["password"]
    assert task.decrypt_credentials[0]["password"] == "keep-reading"

    task.name = "legacy-resave-updated"
    task.save()
    task.refresh_from_db()
    stored = task.credential[0]
    assert stored["credential_id"] == "cred-legacy"
    assert stored.get("system_credential_id")
    assert stored.get("password") in (None, "")
    assert stored_credential_has_secret_blob(task.credential, model_id="host", driver_type="job") is False
    assert task.decrypt_credentials[0]["password"] == "keep-reading"
    assert task.decrypt_credentials[0]["username"] == "ops"


def test_new_task_can_reference_existing_store_id_only():
    stored = ConnectionCredentialService.create(
        name="shared-ssh",
        credential_type="host",
        team=[1],
        payload={"username": "shared", "password": "from-store"},
    )
    task = _create_task(name="id-only-task", credential=[{"credential_id": str(stored.id)}])
    assert task.credential[0]["system_credential_id"] == str(stored.id)
    assert stored_credential_has_secret_blob(task.credential, model_id="host", driver_type="job") is False
    assert task.decrypt_credentials[0]["password"] == "from-store"
    assert task.decrypt_credentials[0]["username"] == "shared"
    assert ConnectionCredential.objects.count() == 1
