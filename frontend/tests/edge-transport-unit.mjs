import assert from "node:assert/strict";
import { backend, api } from "../lib/axios.js";

process.env.EDGE_SHARED_SECRET = "test-edge-secret-" + "a".repeat(48);
process.env.BACKEND_URL = "https://api.example.test";
process.env.CRAWLER_REPORT_API_URL = "https://reports.example.test/admin/crawler/report";
const adapter = async (config) => ({ data: config.headers.toJSON(), status: 200, statusText: "OK", headers: {}, config });
for (const origin of ["https://api.example.test/search", "https://reports.example.test/admin/crawler/report"]) {
  const { data } = await backend.get(origin, { adapter });
  assert.equal(data["X-Edge-Secret"], process.env.EDGE_SHARED_SECRET);
}
for (const origin of ["https://github.com/user", "https://en.wikipedia.org/w/api.php", "https://api.example.test.evil.test/search"]) {
  const { data } = await backend.get(origin, { adapter, headers: { "X-Edge-Secret": "caller-supplied" } });
  assert.equal(data["X-Edge-Secret"], undefined);
}
assert.equal((await api.get("http://localhost/api/search", { adapter })).data["X-Edge-Secret"], undefined);
globalThis.window = {};
assert.equal((await backend.get("https://api.example.test/search", { adapter })).data["X-Edge-Secret"], undefined);
delete globalThis.window;
process.env.BACKEND_URL = "http://api.example.test";
await assert.rejects(backend.get("http://api.example.test/search", { adapter }), /must use HTTPS/);
delete process.env.EDGE_SHARED_SECRET;
assert.equal((await backend.get("http://api.example.test/search", { adapter })).data["X-Edge-Secret"], undefined);
console.log("PASS edge credential: backend-only origins, no browser/provider leak, HTTPS required, local opt-out");
