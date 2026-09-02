from copy import deepcopy

from apps.core.exceptions.base_app_exception import BaseAppException
from apps.core.models.maintainer_info import maintainer_kwargs
from apps.system_mgmt.models.connection_credential import ConnectionCredential

API_SECRET_MASK = "******"

DEFAULT_SECRET_FIELDS = frozenset(
    {
        "accessKey",
        "accessSecret",
        "access_key",
        "access_secret",
        "api_key",
        "app_secret",
        "auth_password",
        "authkey",
        "community",
        "enable_password",
        "password",
        "passphrase",
        "priv_password",
        "private_key",
        "private_key_content",
        "private_key_passphrase",
        "privkey",
        "pwd",
        "secret",
        "secret_key",
        "token",
    }
)


class ConnectionCredentialService:
    """连接凭据的加解密、落库与运行时解析。"""

    @classmethod
    def secret_fields(cls, extra=None):
        fields = set(DEFAULT_SECRET_FIELDS)
        if extra:
            fields.update(extra)
        return fields

    @classmethod
    def create(cls, *, name, credential_type, team, payload, operator="", extra_secret_fields=None, require_team=True):
        name = cls._require_name(name)
        credential_type = cls._require_type(credential_type)
        material = cls._normalize_payload(payload)
        if not material:
            raise BaseAppException("连接凭据内容不能为空")
        instance = ConnectionCredential(
            name=name,
            credential_type=credential_type,
            username=cls._display_username(material),
            payload=cls._encrypt_payload(material, extra_secret_fields),
            team=cls._normalize_team(team, required=require_team),
            **maintainer_kwargs(operator=operator),
        )
        instance.save()
        return instance

    @classmethod
    def update(cls, instance, *, name=None, credential_type=None, team=None, payload=None, operator="", extra_secret_fields=None, require_team=True):
        if name is not None:
            instance.name = cls._require_name(name)
        if credential_type is not None:
            instance.credential_type = cls._require_type(credential_type)
        if team is not None:
            instance.team = cls._normalize_team(team, required=require_team)
        if payload is not None:
            incoming = cls._normalize_payload(payload)
            merged = cls._merge_payload(cls.resolve_instance(instance, extra_secret_fields), incoming, extra_secret_fields)
            instance.payload = cls._encrypt_payload(merged, extra_secret_fields)
            instance.username = cls._display_username(merged)
        if operator:
            maintainer = maintainer_kwargs(operator=operator, include_created=False)
            instance.updated_by = maintainer["updated_by"]
            instance.updated_by_domain = maintainer["updated_by_domain"]
        instance.save()
        return instance

    @classmethod
    def upsert(cls, *, credential_id=None, name, credential_type, team, payload, operator="", extra_secret_fields=None):
        instance = cls.get(credential_id) if credential_id not in (None, "") else None
        if instance is None:
            return cls.create(
                name=name,
                credential_type=credential_type,
                team=team,
                payload=payload,
                operator=operator,
                extra_secret_fields=extra_secret_fields,
                require_team=False,
            )
        return cls.update(
            instance,
            name=name,
            credential_type=credential_type,
            team=team,
            payload=payload,
            operator=operator,
            extra_secret_fields=extra_secret_fields,
            require_team=False,
        )

    @classmethod
    def get(cls, credential_id):
        if credential_id in (None, ""):
            return None
        try:
            return ConnectionCredential.objects.filter(pk=int(credential_id)).first()
        except (TypeError, ValueError):
            return None

    @classmethod
    def resolve(cls, credential_id, extra_secret_fields=None):
        instance = cls.get(credential_id)
        if instance is None:
            return None
        return cls.resolve_instance(instance, extra_secret_fields)

    @classmethod
    def resolve_instance(cls, instance, extra_secret_fields=None):
        payload = deepcopy(instance.payload or {})
        if not isinstance(payload, dict):
            return {}
        for field in cls.secret_fields(extra_secret_fields):
            ConnectionCredential.decrypt_field(field, payload)
        return payload

    @classmethod
    def mask_payload(cls, payload, extra_secret_fields=None):
        masked = deepcopy(payload or {})
        if not isinstance(masked, dict):
            return {}
        for field in cls.secret_fields(extra_secret_fields):
            if masked.get(field) not in (None, ""):
                masked[field] = API_SECRET_MASK
        return masked

    @classmethod
    def public_list_fields(cls, instance):
        return {
            "id": instance.id,
            "name": instance.name,
            "credential_type": instance.credential_type,
            "username": instance.username,
            "team": list(instance.team or []),
            "created_at": instance.created_at,
            "updated_at": instance.updated_at,
            "created_by": instance.created_by,
            "updated_by": instance.updated_by,
        }

    @classmethod
    def _encrypt_payload(cls, payload, extra_secret_fields=None):
        encrypted = deepcopy(payload)
        for field in cls.secret_fields(extra_secret_fields):
            ConnectionCredential.encrypt_field(field, encrypted)
        return encrypted

    @classmethod
    def _merge_payload(cls, existing, incoming, extra_secret_fields=None):
        merged = deepcopy(existing) if isinstance(existing, dict) else {}
        secret_fields = cls.secret_fields(extra_secret_fields)
        for key, value in incoming.items():
            if key in secret_fields and value in (None, "", API_SECRET_MASK):
                continue
            merged[key] = value
        return merged

    @staticmethod
    def _normalize_payload(payload):
        if payload in (None, ""):
            return {}
        if not isinstance(payload, dict):
            raise BaseAppException("连接凭据内容格式错误")
        return deepcopy(payload)

    @staticmethod
    def _normalize_team(team, *, required=True):
        if team in (None, ""):
            if required:
                raise BaseAppException("请选择组织")
            return []
        if isinstance(team, (int, str)):
            team = [team]
        if not isinstance(team, (list, tuple, set)):
            raise BaseAppException("组织格式错误")
        normalized = []
        for item in team:
            try:
                normalized.append(int(item))
            except (TypeError, ValueError) as exc:
                raise BaseAppException("组织格式错误") from exc
        if not normalized and required:
            raise BaseAppException("请选择组织")
        return normalized

    @staticmethod
    def _require_name(name):
        text = str(name or "").strip()
        if not text:
            raise BaseAppException("请输入凭据名称")
        return text

    @staticmethod
    def _require_type(credential_type):
        text = str(credential_type or "").strip()
        if not text:
            raise BaseAppException("请选择凭据类型")
        return text

    @staticmethod
    def _display_username(payload):
        if not isinstance(payload, dict):
            return ""
        for key in ("username", "user", "sec_name"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""
