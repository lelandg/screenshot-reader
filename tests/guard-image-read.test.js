// Run with: node --test tests/guard-image-read.test.js
const { test } = require("node:test");
const assert = require("node:assert");
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const HOOK = path.join(__dirname, "..", "hooks", "guard-image-read.js");

function runHook(input, env = {}) {
  const home = env.HOME || fs.mkdtempSync(path.join(os.tmpdir(), "srhome-"));
  const res = spawnSync(process.execPath, [HOOK], {
    input: typeof input === "string" ? input : JSON.stringify(input),
    encoding: "utf8",
    env: { ...process.env, HOME: home, USERPROFILE: home, SCREENSHOT_READER_ALLOW_DIRECT: "", ...env },
  });
  assert.strictEqual(res.status, 0, res.stderr);
  return { out: res.stdout ? JSON.parse(res.stdout) : null, home };
}

const denied = (r) => r.out && r.out.hookSpecificOutput.permissionDecision === "deny";

test("main-thread Read of an image is denied", () => {
  assert.ok(denied(runHook({ tool_name: "Read", tool_input: { file_path: "C:\\shots\\A.PNG" } })));
  assert.ok(denied(runHook({ tool_name: "Read", tool_input: { file_path: "/tmp/b.jpeg" } })));
});

test("subagent Read of an image passes", () => {
  const r = runHook({ tool_name: "Read", tool_input: { file_path: "/tmp/a.png" }, agent_id: "x1", agent_type: "screenshot-reader:screenshot-reader" });
  assert.strictEqual(r.out, null);
});

test("main thread of a --agent session (agent_type only) is still denied", () => {
  assert.ok(denied(runHook({ tool_name: "Read", tool_input: { file_path: "/tmp/a.png" }, agent_type: "my-agent" })));
});

test("non-image reads and other tools pass", () => {
  assert.strictEqual(runHook({ tool_name: "Read", tool_input: { file_path: "/src/a.ts" } }).out, null);
  assert.strictEqual(runHook({ tool_name: "Bash", tool_input: { command: "ls a.png" } }).out, null);
});

test("malformed input never blocks", () => {
  assert.strictEqual(runHook("not json").out, null);
});

test("env override allows direct reads", () => {
  const r = runHook({ tool_name: "Read", tool_input: { file_path: "/tmp/a.png" } }, { SCREENSHOT_READER_ALLOW_DIRECT: "1" });
  assert.strictEqual(r.out, null);
});

test("fresh override file allows, stale one does not", () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "srhome-"));
  fs.mkdirSync(path.join(home, ".claude"));
  const f = path.join(home, ".claude", "screenshot-reader-allow-direct");
  fs.writeFileSync(f, "");
  const input = { tool_name: "Read", tool_input: { file_path: "/tmp/a.png" } };
  assert.strictEqual(runHook(input, { HOME: home }).out, null);
  const old = new Date(Date.now() - 11 * 60 * 1000);
  fs.utimesSync(f, old, old);
  assert.ok(denied(runHook(input, { HOME: home })));
});
