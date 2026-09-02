import pytest
from rest_framework.test import APIClient

from apps.system_mgmt.models import ConnectionCredential
from apps.system_mgmt.services.connection_credential_service import API_SECRET_MASK, ConnectionCredentialService

pytestmark = pytest.mark.django_db

V = "/api/v1/system_mgmt/connection_credential"


def _list_items(response):
    payload = response.data
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        raise AssertionError(f"unexpected list payload: {payload!r}")
    for key in ("items", "results", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = value.get("items") or value.get("results")
            if isinstance(nested, list):
                return nested
    raise AssertionError(f"list response has no items: {payload!r}")


def _super_client():
    from apps.base.models import User as BaseUser

    admin = BaseUser.objects.create_user(username="cred-admin", password="pw", domain="domain.com", locale="en")
    admin.is_superuser = True
    admin.save()
    client = APIClient()
    client.force_authenticate(user=admin)
    client.cookies["current_team"] = "1"
    return client, admin


def _tenant_client(username, group_id, *, is_superuser=False):
    from apps.base.models import User as BaseUser

    user = BaseUser.objects.create_user(username=username, password="pw", domain="domain.com", locale="en")
    user.is_superuser = is_superuser
    user.group_list = [{"id": group_id, "name": f"org-{group_id}"}]
    user.permission = {
        "system-manager": {
            "connection_credential-View",
            "connection_credential-Add",
            "connection_credential-Edit",
            "connection_credential-Delete",
        }
    }
    user.save()
    client = APIClient()
    client.force_authenticate(user=user)
    client.cookies["current_team"] = str(group_id)
    return client, user


def test_create_and_list_omits_secret_material():
    client, _admin = _super_client()
    created = client.post(
        f"{V}/",
        {
            "name": "ssh-prod",
            "credential_type": "host",
            "team": [1],
            "payload": {"username": "root", "password": "s3cret", "port": 22},
        },
        format="json",
    )
    assert created.status_code == 201
    assert created.data["username"] == "root"
    assert created.data["payload"]["password"] == API_SECRET_MASK
    assert created.data["payload"]["username"] == "root"
    assert "s3cret" not in str(created.data)

    listed = client.get(f"{V}/")
    assert listed.status_code == 200
    items = _list_items(listed)
    assert items
    row = next(item for item in items if item["id"] == created.data["id"])
    assert row["name"] == "ssh-prod"
    assert "payload" not in row
    assert "password" not in row
    assert "s3cret" not in str(listed.data)
    assert ConnectionCredential.objects.get(pk=created.data["id"]).payload.get("password") != "s3cret"


def test_retrieve_masks_secrets_and_resolve_returns_plaintext():
    instance = ConnectionCredentialService.create(
        name="db-prod",
        credential_type="mysql",
        team=[1],
        payload={"username": "monitor", "password": "db-pass"},
        operator="alice",
    )
    client, _admin = _super_client()
    detail = client.get(f"{V}/{instance.id}/")
    assert detail.status_code == 200
    assert detail.data["payload"]["password"] == API_SECRET_MASK
    assert "db-pass" not in str(detail.data)
    assert ConnectionCredentialService.resolve(instance.id)["password"] == "db-pass"


def test_update_keeps_old_secret_when_masked_and_delete():
    instance = ConnectionCredentialService.create(
        name="old",
        credential_type="host",
        team=[1],
        payload={"username": "root", "password": "keep-me"},
    )
    client, _admin = _super_client()
    updated = client.put(
        f"{V}/{instance.id}/",
        {
            "name": "renamed",
            "credential_type": "host",
            "team": [1],
            "payload": {"username": "ops", "password": API_SECRET_MASK},
        },
        format="json",
    )
    assert updated.status_code == 200
    assert updated.data["name"] == "renamed"
    assert ConnectionCredentialService.resolve(instance.id)["password"] == "keep-me"
    assert ConnectionCredentialService.resolve(instance.id)["username"] == "ops"

    deleted = client.delete(f"{V}/{instance.id}/")
    # CustomRenderer 将 DELETE 204 改写为 200
    assert deleted.status_code in (200, 204)
    assert ConnectionCredential.objects.filter(pk=instance.id).exists() is False


def test_team_isolation_list_and_retrieve():
    ConnectionCredentialService.create(
        name="team-1",
        credential_type="host",
        team=[1],
        payload={"username": "one", "password": "p1"},
    )
    other = ConnectionCredentialService.create(
        name="team-2",
        credential_type="host",
        team=[2],
        payload={"username": "two", "password": "p2"},
    )
    client, _user = _tenant_client("tenant-a", 1)
    listed = client.get(f"{V}/")
    assert listed.status_code == 200
    items = _list_items(listed)
    names = {item["name"] for item in items}
    assert names == {"team-1"}
    forbidden = client.get(f"{V}/{other.id}/")
    assert forbidden.status_code == 404


def _store_credential(name="shared-ssh"):
    return ConnectionCredentialService.create(
        name=name,
        credential_type="host",
        team=[1],
        payload={"username": "root", "password": "store-secret"},
    )


def test_delete_fails_when_collect_task_references_store_id():
    stored = _store_credential("collect-ref")
    from apps.cmdb.models.collect_model import CollectModels

    CollectModels.objects.create(
        name="uses-store",
        task_type="host",
        driver_type="job",
        model_id="host",
        cycle_value_type="cycle",
        team=[1],
        credential=[{"credential_id": "cred_pool", "system_credential_id": str(stored.id)}],
    )
    client, _admin = _super_client()
    deleted = client.delete(f"{V}/{stored.id}/")
    assert deleted.status_code == 409
    assert "采集任务" in str(deleted.data)
    assert "uses-store" in str(deleted.data)
    assert ConnectionCredential.objects.filter(pk=stored.id).exists()


def test_delete_fails_when_scan_task_references_numeric_credential_id():
    stored = _store_credential("scan-ref")
    from apps.cmdb.models.scan_model import ScanTask

    ScanTask.objects.create(
        name="scan-uses-store",
        team=[1],
        families=["mysql"],
        credentials={"mysql": [{"credential_id": str(stored.id)}]},
    )
    client, _admin = _super_client()
    deleted = client.delete(f"{V}/{stored.id}/")
    assert deleted.status_code == 409
    assert "扫描任务" in str(deleted.data)
    assert ConnectionCredential.objects.filter(pk=stored.id).exists()


def test_delete_fails_when_monitor_instance_references_store_id():
    stored = _store_credential("monitor-ref")
    from apps.monitor.models import MonitorInstance, MonitorObject

    monitor_object = MonitorObject.objects.create(name="Host-cred-guard", display_name="主机", level="base")
    MonitorInstance.objects.create(
        id="mon-cred-guard",
        name="monitor-uses-store",
        monitor_object=monitor_object,
        summary_facts={"system_credential_id": str(stored.id)},
    )
    client, _admin = _super_client()
    deleted = client.delete(f"{V}/{stored.id}/")
    assert deleted.status_code == 409
    assert "监控实例" in str(deleted.data)
    assert ConnectionCredential.objects.filter(pk=stored.id).exists()


def test_pool_key_is_not_treated_as_store_reference():
    from apps.system_mgmt.services.connection_credential_reference import payload_references_store_id

    assert payload_references_store_id({"credential_id": "cred_abc"}, 12) is False
    assert payload_references_store_id({"credential_id": "12"}, 12) is True
    assert payload_references_store_id({"system_credential_id": "12", "credential_id": "cred_abc"}, 12) is True


def test_delete_succeeds_when_credential_is_unreferenced():
    stored = _store_credential("free-cred")
    client, _admin = _super_client()
    deleted = client.delete(f"{V}/{stored.id}/")
    assert deleted.status_code in (200, 204)
    assert ConnectionCredential.objects.filter(pk=stored.id).exists() is False
