import pytest

from apps.cmdb.models.scan_model import ScanTask
from apps.cmdb.services.collect_credential_reference import stored_credential_has_secret_blob
from apps.system_mgmt.models import ConnectionCredential

pytestmark = pytest.mark.django_db


def test_scan_save_migrates_nested_password_to_id_and_keeps_pool_key():
    task = ScanTask.objects.create(
        name="scan-id-ref",
        team=[1],
        families=["mysql"],
        credentials={
            "mysql": [{"credential_id": "cred-db", "username": "monitor", "password": "db-secret"}],
        },
    )
    task.refresh_from_db()
    stored = task.credentials["mysql"][0]
    assert stored["credential_id"] == "cred-db"
    assert stored.get("system_credential_id")
    assert stored.get("password") in (None, "")
    assert stored_credential_has_secret_blob(task.credentials, driver_type="protocol") is False
    assert task.decrypt_credentials["mysql"][0]["password"] == "db-secret"
    assert ConnectionCredential.objects.filter(pk=int(stored["system_credential_id"])).exists()


def test_scan_legacy_nested_still_reads_before_resave():
    task = ScanTask(
        name="scan-legacy",
        team=[1],
        families=["mysql"],
        credentials={"mysql": [{"credential_id": "cred-db", "username": "monitor", "password": "enc-not-used"}]},
    )
    from apps.cmdb.models.collect_model import CollectModels

    task.credentials = {
        "mysql": [{"credential_id": "cred-db", "username": "monitor", "password": CollectModels.encrypt_password("legacy-db")}],
    }
    decrypted = task.decrypt_credentials
    assert decrypted["mysql"][0]["password"] == "legacy-db"
