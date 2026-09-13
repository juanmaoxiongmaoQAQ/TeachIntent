# TeachIntent review demo (at most two minutes)

Use the React Web application described in the [README](../README.md#quick-start).
Start backend and frontend on loopback, open Explore at `http://127.0.0.1:5173`,
and verify the three committed examples and their evaluator panels. This sequence
uses existing artifacts and needs no model call or GPU. Never show `.env`, API
keys, shell history, raw provider errors or personal absolute paths.

| Time | Screen | Suggested narration |
|---|---|---|
| 0–15 s | Explore, corrective feedback | “TeachIntent lets an AI tutor plan its teaching language and delivery before speaking. Hy3 maps lesson content, learner state and a selected teaching intent into an inspectable Speech Plan.” |
| 15–40 s | Physics context, WHAT and HOW | “This learner thinks unchanged speed means zero acceleration. The response acknowledges the valid observation and corrects the missing direction component. Wording and justified delivery controls are separate.” |
| 40–60 s | Evaluator D1, D2 and D6 with grounded highlights | “An independent evaluator checks six frozen dimensions against input and plan evidence. These are matching recorded judgments. The evaluator assesses the Speech Plan, not the WAV.” |
| 60–80 s | Scaffolding, then supportive feedback | “Scaffolding offers the next gamete-listing step instead of supplying all answers. Supportive feedback recognizes successful reasoning; an empty delivery plan can be appropriate.” |
| 80–100 s | Live Studio prompt selector and Intent Compare input form | “Live Studio explicitly selects v0.2, v0.3 or v0.4 and generates a new plan when requested. Intent Compare holds context constant and changes intent using v0.2. No live calls are made in this recorded walkthrough.” |
| 100–115 s | README architecture / renderer boundary | “BatonVoice is an optional reference renderer. Segment-wise synthesis and sequential Web playback improved our observed fidelity and boundaries; local pronunciation variation remains. The contribution is teaching-aware planning, not a new TTS architecture.” |
| 115–120 s | Project disclaimer | “This is a personal open-practice project, not an official Tencent release.” |

If showing previously verified segmented playback, use an available existing
session and its actual audio, or a prior screen recording whose provenance is
known. It is an optional substitution for part of the final 20 seconds, not a
reason to rerun synthesis. A server restart loses live session registrations;
the Web application does not import historical CLI runs. Do not claim the
Explore Qwen3-TTS recordings are Baton recordings.

The Live Studio showcase button loads **input only**. Do not click Generate,
Evaluate or Render for an offline recording. Demonstrating an actual live call
is a separate, explicit owner action; prerecorded Explore results must remain
labeled as recorded. These three scenarios illustrate different intents but
have different contexts, so do not call them an intent-only controlled test.

Before export: duration ≤2:00; readable Chinese text; matching plan/evaluator
provenance; truthful audio labels; no secrets or private paths; personal-project
disclaimer visible. Export video/GIF into `outputs/submission/` and supply the
final media or submission link through the owner's release process. A recording
and link have not been created by this hardening task.
