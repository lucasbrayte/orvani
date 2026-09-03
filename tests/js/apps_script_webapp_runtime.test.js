const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const sourcePath = path.join(
  __dirname,
  "../../apps_script/orvani_sync_webapp.gs"
);
const source = fs.readFileSync(sourcePath, "utf8");
const context = vm.createContext({ console });

vm.runInContext(
  source + `\n;globalThis.OrvaniWebAppRuntime = {
    orvaniHandleAction_: typeof orvaniHandleAction_ === "function"
      ? orvaniHandleAction_
      : undefined,
    doPost: typeof doPost === "function" ? doPost : undefined,
  };`,
  context
);

const core = context.OrvaniWebAppRuntime;

function installRuntime() {
  const nonceCache = new Map();

  context.PropertiesService = {
    getScriptProperties() {
      return {
        getProperty(name) {
          return name === "ORVANI_SYNC_SECRET" ? "a".repeat(64) : null;
        },
      };
    },
  };

  context.CacheService = {
    getScriptCache() {
      return {
        get(key) {
          return nonceCache.has(key) ? nonceCache.get(key) : null;
        },
        put(key, value) {
          nonceCache.set(key, value);
        },
      };
    },
  };

  context.Utilities = {
    Charset: { UTF_8: "UTF_8" },
    computeHmacSha256Signature() {
      return Array(32).fill(0);
    },
  };

  context.ContentService = {
    MimeType: { JSON: "application/json" },
    createTextOutput(text) {
      return {
        text,
        mimeType: null,
        setMimeType(mimeType) {
          this.mimeType = mimeType;
          return this;
        },
      };
    },
  };

  return nonceCache;
}

function signedHealthEvent(nonce = "nonce-health-1234") {
  const envelope = {
    version: "v1",
    action: "health",
    timestamp: Math.floor(Date.now() / 1000),
    nonce,
    payload: {},
    signature: "00".repeat(32),
  };
  const contents = JSON.stringify(envelope);
  return {
    postData: {
      contents,
      length: Buffer.byteLength(contents, "utf8"),
    },
  };
}

test("health action returns service metadata", () => {
  const result = core.orvaniHandleAction_("health", {});
  assert.equal(result.ok, true);
  assert.equal(result.action, "health");
  assert.equal(result.service, "orvani-sync");
  assert.equal(result.version, "v1");
});

test("doPost accepts a signed health request", () => {
  installRuntime();
  const output = core.doPost(signedHealthEvent());
  const body = JSON.parse(output.text);
  assert.equal(body.ok, true);
  assert.equal(body.action, "health");
  assert.equal(body.service, "orvani-sync");
  assert.equal(output.mimeType, "application/json");
});

test("doPost rejects a reused nonce", () => {
  installRuntime();
  const event = signedHealthEvent("nonce-replay-12345");
  const first = JSON.parse(core.doPost(event).text);
  const second = JSON.parse(core.doPost(event).text);
  assert.equal(first.ok, true);
  assert.equal(second.ok, false);
});

test("doPost rejects an oversized request", () => {
  installRuntime();
  const event = signedHealthEvent("nonce-large-12345");
  event.postData.length = 300000;
  const body = JSON.parse(core.doPost(event).text);
  assert.equal(body.ok, false);
});
