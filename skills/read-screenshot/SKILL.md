---
name: read-screenshot
description: Use whenever you need to know what is in a screenshot or other image file (png, jpg, jpeg, gif, webp, bmp) — a user says "look at the screenshot", "see the error in this image", "check _screenshots", names an image path, or you would otherwise Read an image. Delegates the viewing to the cheap screenshot-reader subagent (Haiku) and works from its text report, so the main model never loads image tokens into its context.
---

# Read screenshots through a cheap subagent

Image tokens are expensive on a large model, and once an image is in your
context it is re-sent on every later turn. A small model can read the screen
and hand you exact text instead. So: **do not Read image files yourself.**

## How

1. Collect the absolute path(s) of the image(s). If the user said "the
   screenshot" (singular), use the newest image by modified time in the folder
   they mean (`_screenshots`, the project's screenshot folder, or the path they
   gave).
2. Dispatch the `screenshot-reader` agent (from this plugin it is
   `screenshot-reader:screenshot-reader`) with the Agent tool. In the prompt:
   - the absolute path(s), one per line;
   - the exact question you need answered ("what is the full error text and
     which file/line does the stack trace point to?", "is the Save button
     disabled?", "list every column header in the table");
   - any context that tells the reader what to focus on (the feature you are
     debugging, the text you expect to see).
3. Work from the report. Quote its verbatim text when you act on it (search
   the codebase for the exact error string, the file path, the line number).
4. If the report is unclear or misses something, ask the reader again with a
   narrower question rather than opening the image yourself.

## Pick the reader's model by the question

The agent defaults to Haiku. Pass `model` on the Agent call to override it:

- **Haiku (default):** reading text — error messages, logs, stack traces,
  code, form values, chat transcripts, table contents.
- **Sonnet (`model: "sonnet"`):** visual judgment — rendering bugs, colors
  that look wrong, overlays or highlights blending badly, misalignment,
  clipping, "what looks off here?". In testing, Haiku hedged on a subtle
  blend-mode bug in thumbnail-sized images, while Sonnet located every
  affected region and described exactly how it differed. Sonnet is still far
  cheaper than loading the image into a large main model.

Small embedded images (an attachment inside a chat screenshot, a thumbnail)
limit any reader. If the question depends on fine detail, ask the user for the
full-size image.

Several images that need the same question can go in one dispatch. Images
needing different questions can go to parallel dispatches.

## When to break the rule

Read the image yourself only when the user explicitly asks you to look at it
directly, or when the reader has failed twice on the same question (for
example, a fine visual-design judgment it keeps getting wrong). Say that you
are doing so and why.

This plugin's hook blocks direct image reads by the main agent. To make an
allowed exception, write an empty file at
`~/.claude/screenshot-reader-allow-direct` (it unlocks direct reads for 10
minutes), then Read the image. The user can also start Claude Code with
`SCREENSHOT_READER_ALLOW_DIRECT=1` to turn the guard off for the session.

## Pasted images

An image pasted straight into the chat is already in your context; this skill
cannot take it back out. Tell the user once that saving screenshots to a file
and giving you the path is cheaper, then carry on.
