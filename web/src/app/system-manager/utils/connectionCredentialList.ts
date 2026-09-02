import type { ConnectionCredentialListItem } from '@/app/system-manager/api/connection-credential';

const SECRET_KEYS = new Set([
  'payload',
  'password',
  'community',
  'token',
  'private_key',
  'passphrase',
  'authkey',
  'privkey',
]);

export function toConnectionCredentialListRow(
  item: ConnectionCredentialListItem
): ConnectionCredentialListItem {
  return {
    id: item.id,
    name: item.name,
    credential_type: item.credential_type,
    username: item.username,
    team: Array.isArray(item.team) ? item.team : [],
    created_at: item.created_at,
    updated_at: item.updated_at,
    created_by: item.created_by,
    updated_by: item.updated_by,
  };
}

export function listRowHasSecretMaterial(row: Record<string, unknown>): boolean {
  return Object.keys(row).some((key) => SECRET_KEYS.has(key));
}
