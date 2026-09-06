import assert from 'node:assert/strict';
import {
  buildPlatformApiCredential,
  createPlatformApiCredential,
  restorePlatformApiCredential,
  validatePlatformApiCredential,
} from '../src/app/cmdb/(pages)/assetManage/autoDiscovery/collection/profess/components/platformApiCredential';
import { getCredentialDescriptor } from '../src/app/cmdb/(pages)/assetManage/autoDiscovery/collection/profess/components/credentialDescriptors';

assert.equal(createPlatformApiCredential('fusioninsight').port, 443);
assert.equal(createPlatformApiCredential('storage').port, 8088);
assert.equal(createPlatformApiCredential('dell_unity').port, 443);
assert.equal(createPlatformApiCredential('dell_powerstore').port, 443);
assert.equal(createPlatformApiCredential('netapp_ontap').port, 443);
assert.equal(createPlatformApiCredential('pure_array').port, 443);
assert.equal(createPlatformApiCredential('hds_vsp').port, 443);
assert.equal(createPlatformApiCredential('hp_3par').port, 443);
assert.deepEqual(
  buildPlatformApiCredential('storage', {
    username: ' admin ',
    password: ' secret ',
    port: 8088,
    verify_tls: false,
  }),
  {
    username: 'admin',
    accessKey: 'admin',
    password: 'secret',
    accessSecret: 'secret',
    port: 8088,
    verify_tls: false,
  },
);
assert.equal(
  buildPlatformApiCredential('fusioninsight', {
    username: 'admin',
    password: '******',
    port: 443,
    verify_tls: true,
  }).password,
  undefined,
);
assert.equal(
  restorePlatformApiCredential(
    'storage',
    { username: 'admin', password: '******', port: 8088 },
    true,
  ).password,
  '',
);
assert.deepEqual(
  restorePlatformApiCredential(
    'fusioninsight',
    { accessKey: 'legacy-user', accessSecret: '******' },
    false,
    'https://fi.example.com:9443/web',
  ),
  {
    username: 'legacy-user',
    password: '******',
    port: 9443,
    verify_tls: true,
  },
);
assert.equal(
  validatePlatformApiCredential({
    username: 'admin',
    password: 'secret',
    port: 443,
  }),
  null,
);

assert.equal(
  getCredentialDescriptor({ model_id: 'fusioninsight' })?.formKind,
  'platform_api',
);
assert.equal(
  getCredentialDescriptor({ model_id: 'storage' })?.formKind,
  'platform_api',
);
assert.equal(
  getCredentialDescriptor({ model_id: 'h3c_cas' })?.formKind,
  'platform_api',
);
assert.equal(
  getCredentialDescriptor({ model_id: 'h3c_cas' })?.defaultPort,
  443,
);
assert.equal(
  getCredentialDescriptor({ model_id: 'fusioncompute' })?.defaultPort,
  7443,
);
assert.equal(
  getCredentialDescriptor({ model_id: 'zstack' })?.defaultPort,
  8080,
);
assert.equal(
  getCredentialDescriptor({ model_id: 'aws' })?.formKind,
  'cloud',
);
for (const modelId of [
  'openstack',
  'smartx',
  'manageone',
  'nutanixhci',
  'sangforhci',
  'sangforscp',
  'inspurincloudrail',
  'azure',
  'dell_unity',
  'dell_powerstore',
  'netapp_ontap',
  'pure_array',
  'hds_vsp',
  'hp_3par',
]) {
  assert.equal(
    getCredentialDescriptor({ model_id: modelId })?.formKind,
    'platform_api',
    modelId,
  );
}

console.log('CMDB platform API credential contract passed');
