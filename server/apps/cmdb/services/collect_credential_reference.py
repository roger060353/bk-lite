"""采集/扫描任务凭据：新写入只存系统管理 ID，旧嵌套密码只读兼容一版。"""

from copy import deepcopy

from apps.cmdb.services.collect_credential_contract import API_SECRET_MASK
from apps.cmdb.services.encrypt_collect_password import get_collect_model_passwords
from apps.system_mgmt.services.connection_credential_service import DEFAULT_SECRET_FIELDS, ConnectionCredentialService

REFERENCE_KEYS = frozenset({"credential_id", "credential_version", "system_credential_id"})


def secret_fields_for(model_id, driver_type=None):
    fields = set(DEFAULT_SECRET_FIELDS)
    fields.update(get_collect_model_passwords(collect_model_id=model_id, driver_type=driver_type) or [])
    return fields


def is_store_reference_id(credential_id):
    if credential_id in (None, ""):
        return False
    text = str(credential_id).strip()
    return text.isdigit()


def is_id_only_item(item):
    if not isinstance(item, dict) or not item.get("credential_id"):
        return False
    for key, value in item.items():
        if key in REFERENCE_KEYS:
            continue
        if value not in (None, "", API_SECRET_MASK):
            return False
    return True


def is_id_only_pool(raw_credential):
    if isinstance(raw_credential, dict):
        pool = [raw_credential]
    elif isinstance(raw_credential, list):
        pool = raw_credential
    else:
        return False
    return bool(pool) and all(is_id_only_item(item) for item in pool)


def _decrypt_legacy_secret(value):
    from apps.cmdb.models.collect_model import CollectModels

    if not isinstance(value, str):
        return value
    return CollectModels.decrypt_password(value)


def _material_from_item(item, secret_fields):
    material = {}
    for key, value in item.items():
        if key in REFERENCE_KEYS:
            continue
        if value in (None, API_SECRET_MASK):
            continue
        if key in secret_fields and isinstance(value, str):
            material[key] = _decrypt_legacy_secret(value)
        else:
            material[key] = deepcopy(value)
    return material


def _store_id_from_item(item):
    system_id = item.get("system_credential_id")
    if is_store_reference_id(system_id):
        return str(system_id)
    pool_id = item.get("credential_id")
    if is_store_reference_id(pool_id):
        return str(pool_id)
    return None


def _reference_item(*, pool_id, store_id, version=1):
    reference = {
        "credential_id": str(pool_id or store_id),
        "system_credential_id": str(store_id),
    }
    if version is not None:
        reference["credential_version"] = version
    return reference


def persist_item(item, *, name, credential_type, team, operator="", secret_fields=None):
    if not isinstance(item, dict):
        return item
    version = item.get("credential_version", 1)
    fields = secret_fields or secret_fields_for(credential_type)
    store_id = _store_id_from_item(item)
    pool_id = item.get("credential_id")
    if is_id_only_item(item) and store_id:
        return _reference_item(pool_id=pool_id, store_id=store_id, version=version)

    material = _material_from_item(item, fields)
    if not material and store_id:
        return _reference_item(pool_id=pool_id, store_id=store_id, version=version)
    if not material:
        return item

    stored = ConnectionCredentialService.upsert(
        credential_id=store_id,
        name=name,
        credential_type=credential_type,
        team=team or [],
        payload=material,
        operator=operator or "",
        extra_secret_fields=fields,
    )
    return _reference_item(pool_id=pool_id, store_id=stored.id, version=version)


def persist_collect_credential(raw_credential, *, name, credential_type, team, operator="", driver_type=None):
    fields = secret_fields_for(credential_type, driver_type)
    kwargs = {
        "credential_type": credential_type,
        "team": team,
        "operator": operator,
        "secret_fields": fields,
    }
    if isinstance(raw_credential, dict):
        return persist_item(raw_credential, name=name, **kwargs)
    if isinstance(raw_credential, list):
        persisted = []
        for index, item in enumerate(raw_credential):
            item_name = name if len(raw_credential) == 1 else f"{name}-{index + 1}"
            persisted.append(persist_item(item, name=item_name, **kwargs))
        return persisted
    return raw_credential


def persist_scan_credentials(raw_credentials, *, name, team, operator=""):
    if not isinstance(raw_credentials, dict):
        return raw_credentials
    persisted = {}
    for model_id, pool in raw_credentials.items():
        persisted[model_id] = persist_collect_credential(
            pool,
            name=f"{name}-{model_id}" if name else model_id,
            credential_type=model_id,
            team=team,
            operator=operator,
        )
    return persisted


def resolve_item(item, *, model_id, driver_type=None):
    if not isinstance(item, dict):
        return item
    fields = secret_fields_for(model_id, driver_type)
    resolved = deepcopy(item)
    store_id = _store_id_from_item(item)
    if store_id:
        payload = ConnectionCredentialService.resolve(store_id, extra_secret_fields=fields)
        if payload:
            merged = deepcopy(payload)
            merged["credential_id"] = str(item.get("credential_id") or store_id)
            merged["system_credential_id"] = str(store_id)
            if item.get("credential_version") is not None:
                merged["credential_version"] = item.get("credential_version")
            for key, value in item.items():
                if key in REFERENCE_KEYS:
                    continue
                if value in (None, "", API_SECRET_MASK):
                    continue
                merged[key] = _decrypt_legacy_secret(value) if key in fields else deepcopy(value)
            return merged

    for field in fields:
        if resolved.get(field):
            resolved[field] = _decrypt_legacy_secret(resolved[field])
    return resolved


def resolve_collect_credential(raw_credential, *, model_id, driver_type=None):
    if isinstance(raw_credential, dict):
        return resolve_item(raw_credential, model_id=model_id, driver_type=driver_type)
    if isinstance(raw_credential, list):
        return [resolve_item(item, model_id=model_id, driver_type=driver_type) for item in raw_credential]
    return raw_credential


def resolve_scan_credentials(raw_credentials, driver_type_for_model):
    if not isinstance(raw_credentials, dict):
        return raw_credentials
    resolved = {}
    for model_id, pool in raw_credentials.items():
        driver_type = driver_type_for_model(model_id) if callable(driver_type_for_model) else None
        resolved[model_id] = resolve_collect_credential(pool, model_id=model_id, driver_type=driver_type)
    return resolved


def stored_credential_has_secret_blob(raw_credential, *, model_id=None, driver_type=None):
    """任务 JSON 是否仍嵌套密钥（用于测试锁定新写入）。"""
    fields = secret_fields_for(model_id, driver_type) if model_id else DEFAULT_SECRET_FIELDS

    def _has_secret(item):
        if not isinstance(item, dict):
            return False
        return any(item.get(field) not in (None, "") for field in fields)

    if isinstance(raw_credential, dict):
        if raw_credential and all(not isinstance(value, (dict, list)) for value in raw_credential.values()):
            return _has_secret(raw_credential)
        return any(stored_credential_has_secret_blob(value, model_id=key, driver_type=driver_type) for key, value in raw_credential.items())
    if isinstance(raw_credential, list):
        return any(_has_secret(item) for item in raw_credential)
    return False
