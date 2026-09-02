from rest_framework import serializers

from apps.core.exceptions.base_app_exception import BaseAppException
from apps.core.utils.serializers import UsernameSerializer
from apps.system_mgmt.models.connection_credential import ConnectionCredential
from apps.system_mgmt.services.connection_credential_service import ConnectionCredentialService


class ConnectionCredentialListSerializer(UsernameSerializer):
    class Meta:
        model = ConnectionCredential
        fields = (
            "id",
            "name",
            "credential_type",
            "username",
            "team",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        )


class ConnectionCredentialSerializer(UsernameSerializer):
    payload = serializers.JSONField(required=False)

    class Meta:
        model = ConnectionCredential
        fields = (
            "id",
            "name",
            "credential_type",
            "username",
            "team",
            "payload",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "domain",
            "updated_by_domain",
        )
        read_only_fields = (
            "id",
            "username",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "domain",
            "updated_by_domain",
        )

    def validate_name(self, value):
        text = str(value or "").strip()
        if not text:
            raise serializers.ValidationError("请输入凭据名称")
        return text

    def validate_credential_type(self, value):
        text = str(value or "").strip()
        if not text:
            raise serializers.ValidationError("请选择凭据类型")
        return text

    def validate_team(self, value):
        try:
            return ConnectionCredentialService._normalize_team(value)
        except BaseAppException as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate_payload(self, value):
        if value in (None, ""):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("连接凭据内容格式错误")
        return value

    def create(self, validated_data):
        operator = getattr(getattr(self.context.get("request"), "user", None), "username", "")
        instance = ConnectionCredentialService.create(
            name=validated_data.get("name"),
            credential_type=validated_data.get("credential_type"),
            team=validated_data.get("team"),
            payload=validated_data.get("payload") or {},
            operator=operator,
        )
        return instance

    def update(self, instance, validated_data):
        operator = getattr(getattr(self.context.get("request"), "user", None), "username", "")
        return ConnectionCredentialService.update(
            instance,
            name=validated_data.get("name"),
            credential_type=validated_data.get("credential_type"),
            team=validated_data.get("team"),
            payload=validated_data.get("payload"),
            operator=operator,
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        resolved = ConnectionCredentialService.resolve_instance(instance)
        data["username"] = instance.username or ConnectionCredentialService._display_username(resolved)
        data["payload"] = ConnectionCredentialService.mask_payload(resolved)
        return data
