import pytest

from apps.cmdb.models.scan_model import ScanExecution, ScanFamilyRun, ScanHit, ScanTask

pytestmark = pytest.mark.django_db


def test_scan_task_defaults_auto_push_off():
    task = ScanTask.objects.create(
        name="scan-model-probe",
        team=["1"],
        ip_ranges=[],
        families=[],
        credentials={},
    )
    assert task.auto_push_monitor is False
    assert task.auto_generate_collect is False


def test_scan_task_encrypts_credentials_per_family_on_save():
    task = ScanTask.objects.create(
        name="scan-encrypt-probe",
        team=["1"],
        families=["mysql", "network"],
        credentials={
            "mysql": [{"credential_id": "cred-db", "username": "monitor", "password": "db-secret"}],
            "network": [{"credential_id": "cred-snmp", "version": "v2c", "community": "public"}],
        },
    )
    task.refresh_from_db()
    mysql_item = task.credentials["mysql"][0]
    network_item = task.credentials["network"][0]
    assert mysql_item.get("password") in (None, "")
    assert network_item.get("community") in (None, "")
    assert mysql_item.get("system_credential_id")
    assert network_item.get("system_credential_id")
    assert mysql_item["credential_id"] == "cred-db"
    assert task.decrypt_credentials["mysql"][0]["username"] == "monitor"


def test_scan_task_decrypt_credentials_returns_plaintext_per_family():
    task = ScanTask.objects.create(
        name="scan-decrypt-probe",
        team=["1"],
        families=["mysql"],
        credentials={
            "mysql": [{"credential_id": "cred-db", "username": "monitor", "password": "db-secret"}],
        },
    )
    decrypted = task.decrypt_credentials
    assert decrypted["mysql"][0]["password"] == "db-secret"
    assert decrypted["mysql"][0]["username"] == "monitor"
    assert task.credentials["mysql"][0].get("password") in (None, "")
    assert task.credentials["mysql"][0].get("system_credential_id")


def test_scan_execution_and_hit_can_be_created():
    task = ScanTask.objects.create(name="scan-exec-probe", team=["1"])
    execution = ScanExecution.objects.create(task=task, status=ScanExecution.STATUS_PENDING)
    family_run = ScanFamilyRun.objects.create(
        execution=execution,
        model_id="mysql",
        driver_type="protocol",
    )
    hit = ScanHit.objects.create(
        execution=execution,
        family_run=family_run,
        protocol="mysql",
        host="10.0.1.20",
        port=3306,
        credential_id="cred-db",
        status=ScanHit.STATUS_SUCCESS,
    )
    assert execution.claim_token == ""
    assert execution.target_count == 0
    assert family_run.received_count == 0
    assert hit.inst_uuid == ""
