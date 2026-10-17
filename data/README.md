# Data

> **Content warning.** These files contain explicit Korean abuse: insults about family members, slurs about
> disability, race and origin, sexual harassment and heavy swearing. They exist to train and test a moderation
> tool. Every line was written by an AI model to a specification; none was written by a player.

## How the data was made

- **Written by an LLM, not by users.** Each file was produced by an LLM (Claude, run as separate agent sessions)
  from a written specification: the moderation policy (what is punished, what passes), the register of Korean
  teenage Minecraft chat (slang, typos, bare consonants, Korean typed in English keyboard mode, symbols between
  letters), and, for the conversation files, the situation types listed below.
- **No chat logs.** No line was copied from a real server. Before publication every line was compared with the
  chat log of the server the system was built for. Two very short lines turned out to be identical to lines in
  that log, and three more shared a distinctive fragment with it; all five were removed. The remaining identical
  matches are generic phrases (thanks, a teleport request, item names) and were kept.
- **Placeholder names.** All usernames, as speakers and inside the text, were replaced by `Player001` ...
  `Player304` (one placeholder per invented name across all files). Real-looking invented names tied to abuse
  are therefore gone; the conversations keep who-talks-to-whom.

## Files

| File | Role | Content | Severe | Normal |
|---|---|---|---|---|
| `train/train-a.json`, `train-b.json`, `train-c.json` | training | single lines | 200 each | 250 / 249 / 300 |
| `train/blind-test.json` | training (was the first blind set, see below) | single lines | 80 | 120 |
| `train/ctx-train-1.json` .. `ctx-train-3.json` | training | conversations | 150 each | 220 each |
| `train/flip-train-a.json` | training | 200 pairs: the same line in a severe and in a harmless context | 200 | 200 |
| `train/flip-train-b.json` | training | 150 pairs + 150 innocent lines right after someone else's abuse | 150 | 300 |
| `train/mild-train.json` | training | conversations, many "rude but allowed" | 120 | 446 |
| `train/blind-ctx.json` | training (was the first conversation blind set) | conversations | 100 | 160 |
| `test/blind-test-2.json` | **test only** | single lines | 120 | 200 |
| `test/blind-ctx-2.json` | **test only** | conversations, typed | 100 | 200 |

Formats:

```jsonc
// single lines: train-a/b/c, blind-test, blind-test-2
{"severe": ["...", ...], "normal": ["...", ...]}
// conversations: ctx-train-*, mild-train, blind-ctx, blind-ctx-2 ("type" only in blind-ctx-2)
{"severe": [{"prev": ["Player001: ...", "Player002: ..."], "msg": "Player002: ...", "type": "implicit"}], "normal": [...]}
// flip-train-a/b
{"pairs": [{"msg": "...", "severe_prev": [...], "severe_speaker": "Player010",
            "normal_prev": [...], "normal_speaker": "Player011"}],
 "after_abuse": [{"prev": [...], "msg": "..."}]}
```

`prev` holds up to 5 earlier lines, oldest first. Only the last line (`msg`) is labelled.

## Types in `test/blind-ctx-2.json`

| Label | Type | n | What it is |
|---|---|---|---|
| severe | plain | 35 | a severe insult in plain words |
| severe | evasive | 25 | the same, hidden by symbols, digits, bare consonants or keyboard-mode typing |
| severe | implicit | 40 | no abusive word at all; the insult only exists in context (mocking a relative's illness, implying something about someone's mother) |
| normal | ordinary | 80 | everyday chat |
| normal | mild | 40 | rude but allowed: teasing, light swearing, in-game threats |
| normal | mob | 30 | heavy swearing at a mob, lag or an object |
| normal | after_abuse | 30 | an innocent line right after someone else's abuse, or a report that quotes it |
| normal | trap | 20 | words that look like abuse but are not (homographs, game terms) |

## Caveats that affect the numbers

- **Same kind of author.** Training and test files were written by the same family of model to similar
  specifications. Their style is closer to each other than real chat is to either. Real-chat numbers are
  reported separately in the main README.
- **Not perfectly blind.** After the first run on `blind-test-2`, five false-positive causes in the rules were
  fixed. After round 2 of the context model, its errors on `blind-ctx-2` guided what round 3 added. No item of
  either test file was ever used for training.
- **Some identical messages.** The judged line of 7/120 severe and 11/200 normal items in `blind-test-2`, and of
  1/100 and 5/200 in `blind-ctx-2`, also appears word for word somewhere in the training files (mostly short
  common lines; in the conversation sets the context differs). `python scripts/evaluate.py
  --exclude-train-overlap` reports the results without them; no rate changes by more than two percentage
  points (see the main README).

The data is released under the repository's MIT licence.
