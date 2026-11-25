// 継手APIに適用するIBM API Handbookの設計規則。
const ibm = require('@ibm-cloud/openapi-ruleset');
module.exports = {
  extends: [[ibm, 'off']],
  rules: {
    'ibm-operation-responses': 'error',
    'ibm-content-contains-schema': 'error',
    'ibm-error-content-type-is-json': 'error',
    'ibm-define-required-properties': 'error',
    'ibm-parameter-schema-or-content': 'error',
    'ibm-valid-path-segments': 'error',
    'ibm-pagination-style': 'warn',
  },
};
