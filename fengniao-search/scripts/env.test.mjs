import test from "node:test";
import assert from "node:assert/strict";
import { BASE_URL, getApiKey } from "./env.mjs";

const ENV_KEY = "FN_API_KEY";

async function withApiKey(value, fn) {
  const original = process.env[ENV_KEY];
  if (value == null) {
    delete process.env[ENV_KEY];
  } else {
    process.env[ENV_KEY] = value;
  }

  try {
    await fn();
  } finally {
    if (original == null) {
      delete process.env[ENV_KEY];
    } else {
      process.env[ENV_KEY] = original;
    }
  }
}

test("getApiKey reads only FN_API_KEY", async () => {
  await withApiKey("fn_sk_user_private_key", async () => {
    assert.equal(await getApiKey(), "fn_sk_user_private_key");
  });
});

test("getApiKey returns empty when FN_API_KEY is not configured", async () => {
  await withApiKey(null, async () => {
    assert.equal(await getApiKey(), "");
  });
});

test("getApiKey ignores placeholder values", async () => {
  await withApiKey("YOUR_API_KEY", async () => {
    assert.equal(await getApiKey(), "");
  });
});

test("default base url targets the production package", () => {
  assert.equal(BASE_URL, "https://m.riskbird.com/prod-qbb-api");
});
