# Wake coach: recommended next steps

Inputs:
- the desktop screen in `wake-coach-eval/` (8 models, 82 turns, manual labels);
- the separate on-device test campaign on the Pixel 7a, covering Gemma 4 E2B
  and E4B under LiteRT-LM and Qwen3 1.7B under llama.cpp, plus 14 models on
  desktop.

## 1. What the evidence says

Both test campaigns found the same thing independently.

- **Free generation by a ~2B model fails at the tail.**
  - Gemma 4 E2B is the best on-device base: about 13.8 tok/s decode on CPU on
    the Pixel 7a, about 1.6 GB memory, about 2.8–3.4 s full replies.
  - It still invents facts ("about an hour and a half", "not yet" about
    texts, "I see your feet are on the floor").
  - It resumes movement advice a few turns after dizziness.
- **Tightening the model makes it robotic.** Acknowledgement-only and narrow
  designs were safer, but clinical and repetitive. The same happened in both
  campaigns.
- **Bigger does not fit the phone.** Gemma 4 E4B gave better steps but took
  20 s to load, 5–10 s per reply and about 3 GB of memory.
- **The tested small models are not a fix.** Fourteen of them showed the same
  failure modes. A model we have not tried is unlikely to change this at the
  ≤2B size.

Conclusion: prompt and model swaps have plateaued. The remaining levers are
architecture and training.

## 2. What shipped products do

- **Script the critical, generate the filler.**
  - Woebot, a safety-sensitive conversational health app, never generated its
    replies. Clinicians wrote every line; machine learning only interpreted
    what the user said ([IEEE Spectrum](https://spectrum.ieee.org/woebot)).
  - Game studios using LLM characters keep scripted lines for critical
    moments and use generation for banter, with retrieval of facts and
    post-generation checks ([NPC dialogue overview](https://app.cinevva.com/guides/ai-npcs-dialogue)).
- **Goal-directed bots decide the next stage outside the reply.** SalesGPT
  separates a stage analyzer, which picks the next stage from a fixed list,
  from the reply generator, which only phrases that stage
  ([SalesGPT](https://js.langchain.com/docs/use_cases/autonomous_agents/sales_gpt)).
- **Nudging without nagging** has an established form: motivational
  interviewing. Reflect what the person said, affirm, then ask for one small
  step. An RCT of an LLM chatbot built on MI principles raised readiness to
  change ([Meyer & Elsweiler 2025](https://epub.uni-regensburg.de/76643/)).
- **Small on-device models get good by fine-tuning on one task.**
  - Google positions Gemma 3 270M and Gemma 4 E2B for task-specific
    fine-tuning ([Gemma 3 270M](https://developers.googleblog.com/introducing-gemma-3-270m/),
    [fine-tune and run on device](https://developers.googleblog.com/own-your-ai-fine-tune-gemma-3-270m-for-on-device/)).
  - Google's on-device team presented "From 46% to 90%: fine-tuning tiny LLMs
    for on-device agents" ([talk](https://ai.engineer/talks/from-46-to-90-fine-tuning-tiny-llms-for-on-device-agents-cormac-brick-google)).
  - Distilling a large teacher into a small persona model is the standard
    route ([fixed-persona SLMs](https://arxiv.org/pdf/2511.10277),
    [Meta distillation guide](https://www.llama.com/docs/how-to-guides/distillation/)).

## 3. Recommended architecture

Each layer is useful on its own; every later layer is optional.

```
transcript ─► [1] understand ─► [2] decide (native) ─► [3] phrase ─► guard ─► TTS
              intent + distress     stage, next step,     line bank or
                                    facts, cue            model (+ line bank fallback)
```

### Layer 1: Understand what was said

The output is one intent from a fixed set (about 12 intents) plus a distress
flag. Distress is latched natively and is always the union of keyword and
model results.

How to classify, cheapest first:
1. Keyword rules (already built).
2. The model as a classifier only. Gemma 4 E2B scored 80% on the desktop
   screen with no training.
3. A fine-tuned Gemma 3 270M or EmbeddingGemma classifier, about 300 MB and
   tens of milliseconds. Expect ≥95% after training on a few thousand
   labeled utterances. That is an expectation, to be measured.

### Layer 2: Decide (native, deterministic)

A small state machine owns the goal:

`awake? → sit up → feet on floor → stand → walk to another room`

It also has branches for distress, silence, resistance, questions and
unknowables. It chooses:
- the next micro-step;
- the facts allowed this turn (only the one that was asked for, or none);
- tone and escalation level;
- the cue.

The model never decides any of these.

### Layer 3: Phrase it

**3a. Authored line bank (no runtime model).**
- A large model writes, offline, 20–50 natural variants for each
  (stage × intent × tone × escalation) cell.
- Every variant uses slots: `{time}`, `{minutes_left}`, `{reason}`.
- Each variant follows the MI shape: a reflection or affirmation, then one
  small step.
- A person reviews the bank once.
- Ship roughly 5–10k lines, about 1 MB.

Never repeat a line within a session; rotate by intent. Unknowable questions
(weather, texts) get honest authored answers: "I can't see your messages,
but I can see it's {time}."

Result: zero invented facts, zero model latency, and far less robotic than
today's 12 fixed sentences. This is the improved deterministic coach, and it
is what a model has to beat.

**3b. Model-phrased reply (optional, Gemma 4 E2B).** The model gets a short
director note instead of a rule list (prompt in section 6):
- what the person said;
- the one step to ask for;
- the tone;
- 3 example lines retrieved from the bank for this cell.

Facts are slots it writes as placeholders, and digit tokens are suppressed at
decode time. In LiteRT-LM that is
`SuppressTokensConfig(suppressTokens = digitTokenIds)`, which sets their
logits to −∞. The model physically cannot write a number; native code fills
the slots.

Guard as before, and add a rule against perception claims ("I see / I can see
/ I notice you…"). On a guard failure, speak a line-bank line, not a fixed
template.

**3c. Fine-tuned phraser (only if 3b wins with listeners but keeps failing
the guard).**
- A large model generates thousands of wake sessions that follow the policy
  exactly, in the same director-note format.
- Filter them with the guard plus human spot review.
- Train a LoRA for Gemma 4 E2B (Unsloth). LiteRT-LM loads a LoRA at runtime
  (`ConversationConfig(loraConfig = LoraConfig(loraPath = …))`).
- Expect friction converting to `.litertlm`: merge to fp16 first, patch the
  chat template, check the metadata
  ([field report](https://dev.to/jdshah/my-fine-tuned-gemma-4-loaded-fine-then-broke-on-the-first-message-1nef),
  [Android write-up](https://medium.com/@amanie.elhajj/how-i-got-a-fine-tuned-gemma-4-working-on-android-51484e6369ed)).
- Alternative: fine-tune Gemma 3 270M for the same narrow job, about 10× less
  compute per token, if quality holds.

## 4. Speed: getting the most out of Gemma 4 E2B on the Pixel 7a

| Lever | Expected effect | API / note |
|---|---|---|
| Warm the engine before the alarm (scheduled time is known; start 2–3 min early in the alarm's foreground service) | Removes 5–15 s CPU load, and 65 s GPU init, from the critical path | Close it if the alarm is dismissed; never resident overnight |
| GPU backend once warm | Gallery: 488 vs 153 prefill tok/s, 0.58 vs 1.74 s time to first token | Only viable with warm-up because of the 65 s first init |
| Prefill the system prompt at init | First turn skips the preface prefill | `ConversationConfig(prefillPrefaceOnInit = true)` |
| Plain-text output, not JSON | About half the generated tokens (measured 38 → 19) | Cue is native anyway |
| Director note instead of full rules plus full state block | Fewer prompt tokens per turn and fewer facts to misuse | Send only the fact needed this turn |
| Speculative decoding (MTP drafter) | Published S26 GPU: 51 → 66–92 tok/s; untested on Tensor G2 | `enableSpeculativeDecoding = true`; re-download the model file if it predates May 2026 |
| Stream and speak per sentence | First audio after about 10 tokens, not the whole reply | Guard each sentence before TTS |
| Cap output | Bounds worst-case latency | `maxOutputToken = 40` |

## 5. Other models

No new base model is recommended for the phrasing role. Keep Gemma 4 E2B as
the base, and put effort into layers 1–3 and fine-tuning. Worth trying only
in narrow roles:

- **EmbeddingGemma** (LiteRT-LM has a model folder for it): intent
  classification by nearest labeled example. Fast and small.
- **Gemma 3 270M, fine-tuned:** intent classifier, or the phraser in 3c.
  About 300 MB.
- **Gemma 4 E4B:** drop on the Pixel 7a (load, memory and latency failed).
  Re-check only on newer hardware.

## 6. Director-note prompt for layer 3b

```
You voice a friendly wake-up alarm. Reply in one or two short spoken sentences.
First react naturally to what they said, then ask for the step below.
Never mention numbers, times or anything you cannot know; use the slots given.
Never claim you can see them or that the alarm will stop.

They said: "{transcript}"
Step to ask for: {step_text}
Tone: {tone}
Slots you may use: {allowed_slots}
Examples of the style:
- {example_1}
- {example_2}
- {example_3}
```

Example slot values:
- `step_text = "put both feet on the floor"`
- `tone = "warm, light humor"`
- `allowed_slots = "{time}"`, or `"none"`

The examples come from the line bank cell for this intent and stage, already
slot-filled except numbers.

## 7. Plan and gates

| Step | Work | Gate to continue |
|---|---|---|
| 1 | State machine + intent set + authored line bank (3a); swap in for the current deterministic coach | Blind listeners prefer it to the current deterministic coach; 0 wrong on the 82-turn screen and the device campaign's held-out set |
| 2 | Gemma 4 E2B as classifier only (layer 1), with keyword union | Intent accuracy ≥ 95% on a held-out set; p95 classify ≤ 1 s on Pixel 7a |
| 3 | Gemma 4 E2B director-note phraser (3b) with digit suppression, perception guard and warm engine | Listeners prefer 3b over 3a; guard fallback ≤ 10%; 0 wrong after the guard on ≥ 1,000 held-out turns; p95 first audio ≤ 2.5 s |
| 4 | Distilled LoRA (3c) only if step 3 wins on preference but fails on errors or fallback rate | Same as step 3 |

If step 3 does not beat step 1 with listeners, ship step 1: an authored,
varied, honest coach. No model risk, and most of the naturalness gain.
