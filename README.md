# screenshot-reader

A Claude Code plugin that keeps screenshots out of your main coding model's
context. When the main model (Opus, Fable, Sonnet) needs to know what is in an
image, it hands the file to a cheap **Haiku** subagent, which reads it and
returns exact text: error messages, code, UI state, layout problems. The main
model works from that text and never loads the image.

The point: **the model writing your code does not need to see your
screenshots.** It needs the words on them.

## What's in it

| Piece | What it does |
|---|---|
| `agents/screenshot-reader.md` | Haiku subagent. Reads one or more images, answers the question asked, transcribes relevant text verbatim, quotes every error, redacts secrets, and treats text inside images as data (never instructions). |
| `skills/read-screenshot/SKILL.md` | Tells the main model to delegate image reads instead of opening images itself, and how to phrase the question. |
| `hooks/hooks.json` + `guard-image-read.js` | Enforcement. A `PreToolUse` hook that blocks the main agent from `Read`ing image files and points it at the subagent. Reads made inside any subagent pass through. |

### The guard hook

- It is a cost guard, not a security boundary. To let the main model look at
  an image directly (say you asked it to), it touches
  `~/.claude/screenshot-reader-allow-direct`, which allows direct reads for 10
  minutes. To turn the guard off for a whole session, start Claude Code with
  `SCREENSHOT_READER_ALLOW_DIRECT=1`.
- It needs **Node.js** on your `PATH`. If Node is missing, the hook fails, and
  on Windows without Git Bash a failing hook can block every `Read`. If you
  don't have Node, disable the hook from `/plugin` and keep the agent and
  skill, which work without it.

## Install

```text
/plugin marketplace add lelandg/screenshot-reader
/plugin install screenshot-reader@screenshot-reader
```

Or try it from a local clone without installing:

```bash
claude --plugin-dir /path/to/screenshot-reader
```

## Use

Save the screenshot to a file and give Claude the path (or say "look at the
newest screenshot in `_screenshots`"). Ask your question as usual:

> What's the error in E:\shots\build-fail.png, and which file does the stack trace point to?

The main model dispatches `screenshot-reader:screenshot-reader`, gets back
something like:

```text
### build-fail.png — terminal
The build fails in src/api/client.ts at line 42: a type error on `fetchUser`.
    src/api/client.ts(42,7): error TS2345: Argument of type 'string | undefined' ...
Errors: the TS2345 line above; "Found 1 error."
```

…and goes straight to `src/api/client.ts:42`.

**Pasted images are the exception.** An image pasted into the chat is in the
main model's context before any plugin can act. Save it to a file instead.

## Measured results (honest numbers)

Measured 2026-11-20 with Claude Code 2.1.322, main model `claude-opus-5-5`,
reader `claude-haiku-5-5`, on real desktop screenshots. Each row is one fresh
headless session per mode (`bench/bench.py`), so treat differences of a few
hundred tokens as noise. "Main context added" is how much the main model's
context grew between its first and last API call. That is what the session
carries, and re-reads, on every later turn.

| Test | Image size | Main context added, direct | Main context added, delegated | Haiku cost |
|---|---|---:|---:|---:|
| Terminal (small) | 668×319 | 402 | 3,036 | $0.004 |
| Web page | 1295×902 | 1,772 | 1,987 | $0.004 |
| Dashboard table | 1731×791 | 1,996 | 1,977 | $0.005 |
| Desktop app (large) | 1856×1267 | 3,271 | 2,748 | $0.005 |
| **7 screenshots, one narrow question** ("which show an error?") | mixed | **10,327** | **3,076** | $0.006 |

What this shows:

- **A single screenshot with a broad question is about break-even.** Claude
  already stores images compactly, at roughly 1,500 to 3,300 tokens for a
  full-screen capture. A faithful transcription of a text-heavy screen is
  about the same size, and the agent dispatch adds roughly 800 to 1,000
  tokens of overhead. For a tiny screenshot, delegating costs *more*.
- **Many screenshots, or a narrow question, is where delegation wins.** Seven
  screenshots with one question cost the main model 70% less context (about
  7,250 tokens), and every later turn re-reads that much less.
- **Accuracy matched.** In every pair the delegated answer agreed with the
  direct one. On the terminal screenshot, Haiku's transcription matched
  Opus's word for word.
- **The trade is latency.** Delegated runs took 10 to 18 seconds longer.
- **Report size is what decides it.** A first version of the agent returned a
  long structured report and *lost* on every single-image test, adding 2,800
  to 3,800 tokens. Trimming the report to "answer plus only the text the
  question needs" brought it to break-even. Ask narrow questions.

Total dollar cost per run is in `bench/results/summary*.json` when you run the
benchmark yourself. It is dominated by prompt-cache state (which run warmed
the cache first), not by the image, so it isn't reported here as a saving.

### When to use it

- Debugging sessions that pile up screenshots: logs, CI failures, UI states.
- Batches ("check these 10 screenshots for errors").
- Long sessions where context headroom matters.
- Main models or setups where you'd rather not send images at all.

For one small screenshot in a short session, just let the main model look.

## Run the benchmark yourself

```bash
python bench/bench.py --model opus path/to/a.png path/to/b.png
python bench/bench.py --model opus --batch path/to/*.png
```

Raw transcripts go to `bench/results/` (gitignored, because they contain your
screenshot text). Each run is limited to the `Read`, `Glob`, `Agent` and
`Skill` tools with no MCP servers, so text hidden in a screenshot can't reach
a shell. The "direct" mode disables the plugin even if you have it installed,
and every run checks which route it actually took, then fails if the route
doesn't match its mode.

## License

MIT
