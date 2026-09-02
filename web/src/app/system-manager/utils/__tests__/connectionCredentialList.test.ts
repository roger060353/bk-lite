import { describe, expect, it } from 'vitest';
import {
  listRowHasSecretMaterial,
  toConnectionCredentialListRow,
} from '@/app/system-manager/utils/connectionCredentialList';

describe('connectionCredentialList', () => {
  it('drops payload and secret fields from list rows', () => {
    const row = toConnectionCredentialListRow({
      id: 7,
      name: 'ssh-prod',
      credential_type: 'host',
      username: 'root',
      team: [1],
      created_at: '2026-09-02T00:00:00Z',
      payload: { password: 's3cret' },
      password: 's3cret',
    } as never);

    expect(row).toEqual({
      id: 7,
      name: 'ssh-prod',
      credential_type: 'host',
      username: 'root',
      team: [1],
      created_at: '2026-09-02T00:00:00Z',
      updated_at: undefined,
      created_by: undefined,
      updated_by: undefined,
    });
    expect(listRowHasSecretMaterial(row as unknown as Record<string, unknown>)).toBe(false);
  });

  it('flags raw API mistakes that still carry secrets', () => {
    expect(listRowHasSecretMaterial({ id: 1, name: 'x', payload: { password: 'x' } })).toBe(true);
    expect(listRowHasSecretMaterial({ id: 1, name: 'x', password: 'x' })).toBe(true);
  });
});
