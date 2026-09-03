const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const gsPath = path.resolve(__dirname, "../../apps_script/orvani_sync_webapp.gs");
const source = fs.readFileSync(gsPath, "utf8") + `
globalThis.OrvaniAppsScriptCore = {
  orvaniCanonicalJson_: typeof orvaniCanonicalJson_ === "function"
    ? orvaniCanonicalJson_
    : undefined,
  orvaniVerifyEnvelopeCore_: typeof orvaniVerifyEnvelopeCore_ === "function"
    ? orvaniVerifyEnvelopeCore_
    : undefined,
};
`;

const context = vm.createContext({
  console,
});
vm.runInContext(source, context, { filename: gsPath });
const core = context.OrvaniAppsScriptCore;

function fakeHmacHex() {
  return "a".repeat(64);
}

function signedEnvelope(overrides = {}) {
  return {
    version: "v1",
    action: "health",
    timestamp: 1000,
    nonce: "nonce_123456789012",
    payload: {},
    signature: "a".repeat(64),
    ...overrides,
  };
}

test("canonical JSON sorts object keys recursively", () => {
  const value = { z: 1, a: { y: 2, b: "ç" }, list: [{ d: 4, c: 3 }] };
  assert.equal(
    core.orvaniCanonicalJson_(value),
    '{"a":{"b":"ç","y":2},"list":[{"c":3,"d":4}],"z":1}'
  );
});

test("verification rejects stale timestamps", () => {
  const envelope = signedEnvelope({ timestamp: 1000 });
  assert.throws(
    () => core.orvaniVerifyEnvelopeCore_(
      envelope, "secret", 1121, fakeHmacHex, () => true
    ),
    /timestamp/i
  );
});

test("verification rejects a reused nonce", () => {
  const envelope = signedEnvelope({ nonce: "nonce_123456789012" });
  assert.throws(
    () => core.orvaniVerifyEnvelopeCore_(
      envelope, "secret", envelope.timestamp, fakeHmacHex, () => false
    ),
    /nonce/i
  );
});
