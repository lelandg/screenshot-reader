#!/usr/bin/env node
// PreToolUse guard: stops the MAIN agent from Reading image files directly and
// points it at the screenshot-reader subagent instead. Reads made inside a
// subagent (the hook input then carries agent_id) pass through. agent_type
// alone is not enough: a session started with `claude --agent X` has
// agent_type on its main thread too.
//
// Overrides (this is a cost guard, not a security boundary):
//   SCREENSHOT_READER_ALLOW_DIRECT=1  - allow direct reads for the session.
//   ~/.claude/screenshot-reader-allow-direct - a file touched less than
//     10 minutes ago allows direct reads (lets the model honor an explicit
//     "look at it yourself" without restarting Claude Code).
// Debug: SCREENSHOT_READER_HOOK_LOG=<file> appends each hook input.

const fs = require("fs");
const os = require("os");
const path = require("path");

// Only formats the Read tool returns as visual content.
const IMAGE_EXT = /\.(png|jpe?g|gif|webp)$/i;
const OVERRIDE_FILE = path.join(os.homedir(), ".claude", "screenshot-reader-allow-direct");
const OVERRIDE_TTL_MS = 10 * 60 * 1000;

function overrideActive() {
  if (process.env.SCREENSHOT_READER_ALLOW_DIRECT === "1") return true;
  try {
    return Date.now() - fs.statSync(OVERRIDE_FILE).mtimeMs < OVERRIDE_TTL_MS;
  } catch {
    return false;
  }
}

let raw = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (c) => (raw += c));
process.stdin.on("end", () => {
  let input;
  try {
    input = JSON.parse(raw);
  } catch {
    process.exit(0); // never block on a parse problem
  }

  if (process.env.SCREENSHOT_READER_HOOK_LOG) {
    try {
      fs.appendFileSync(process.env.SCREENSHOT_READER_HOOK_LOG, raw.trim() + "\n");
    } catch {}
  }

  const file = (input.tool_input && input.tool_input.file_path) || "";
  if (input.tool_name !== "Read" || !IMAGE_EXT.test(file)) process.exit(0);
  if (input.agent_id) process.exit(0); // inside a subagent
  if (overrideActive()) process.exit(0);

  const reason =
    `Image reads are delegated to save context. Dispatch an agent with "${file}" ` +
    `and the exact question: screenshot-reader:visual-inspector (Sonnet) for ` +
    `anything about how it looks (rendering, colors, layout, before/after), or ` +
    `screenshot-reader:screenshot-reader (Haiku) to read text off the screen. ` +
    `Then work from its text report. If the user ` +
    `explicitly asked you to look at the image yourself, create or touch the ` +
    `file ${OVERRIDE_FILE} (valid 10 minutes) and retry the Read.`;

  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: reason,
      },
    })
  );
  process.exit(0);
});
