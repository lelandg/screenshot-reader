#!/usr/bin/env node
// PreToolUse guard: stops the MAIN agent from Reading image files directly and
// points it at the screenshot-reader subagent instead. Reads made inside a
// subagent (the hook input then carries agent_id / agent_type) pass through.
//
// Opt out for one session: set SCREENSHOT_READER_ALLOW_DIRECT=1.
// Debug: set SCREENSHOT_READER_HOOK_LOG=<file> to append each hook input.

const fs = require("fs");

const IMAGE_EXT = /\.(png|jpe?g|gif|webp|bmp|tiff?|heic)$/i;

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

  const path = (input.tool_input && input.tool_input.file_path) || "";
  if (input.tool_name !== "Read" || !IMAGE_EXT.test(path)) process.exit(0);
  if (process.env.SCREENSHOT_READER_ALLOW_DIRECT === "1") process.exit(0);
  if (input.agent_id || input.agent_type) process.exit(0); // inside a subagent

  const reason =
    `Image reads are delegated to save context: dispatch the ` +
    `screenshot-reader:screenshot-reader agent with "${path}" and the exact ` +
    `question you need answered, then work from its text report. ` +
    `(The user can set SCREENSHOT_READER_ALLOW_DIRECT=1 to allow direct reads.)`;

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
