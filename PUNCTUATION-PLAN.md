# Punctuation correction proposal — 2026-11-03

Andrew approved this approach on 2026-11-03. Implementation and qualification are in progress; no completed fix is claimed yet. GOAL.md is the authoritative acceptance record. Andrew requires punctuation in ordinary prose and previously requested agreement on the approach before implementation.

## What the current code does

`dictation/worker.py` transcribes each recording independently with faster-whisper, strips segment-edge whitespace and joins segments with spaces. It does not remove punctuation, but it also does not restore missing punctuation. `Session.finished` stores and pastes that result directly. Consequently, a speech-model result with missing sentence boundaries reaches every recovery surface unchanged. This is established by source inspection; the current user report has not yet been replayed in a fresh VM.

## Recommended approach

1. Keep local Whisper recognition and its GPU/CPU fallback. After recognition, run a dedicated local punctuation model over the completed transcript, before it enters history or the clipboard. Evaluate an ONNX candidate using the runtime already present for VAD; choose and pin a model revision only after output quality and CPU latency are measured. There is no need for an account or a cloud language-model request.
2. Restore periods, commas and question marks within a recording, with conservative sentence casing. Preserve wording and ordering. Guard contractions, names, numbers, URLs/emails and already-punctuated content. Validate that a candidate has not changed the underlying words before accepting it. A Whisper prompt may be evaluated as supporting guidance; it is not the punctuation guarantee.
3. Normalize completion once, then route that same result to automatic insertion, five-result history, Copy and Forward. Empty/no-speech output stays empty. If restoration fails, keep the raw dictation recoverable in memory and show an explicit failure; do not silently auto-paste an unprocessed result. The recovery/retry control must be specified and tested with both frontends.
4. Treat the previously reported joining of two recordings as a separate insertion boundary. Proposed narrow rule: insert one trailing separator after completed ordinary prose, keeping history text clean and never injecting Enter. Test this against repeated paste and literal/protected content before accepting it. Do not inspect arbitrary surrounding editor text or globally rewrite the clipboard to infer context.
5. Add explicit setup/download handling for the selected punctuation weights, offline loading and bounded CPU inference. A CPU punctuation pass avoids requiring another GPU allocation while Whisper is loaded. Check startup, idle memory, shutdown, failed downloads and the frozen Windows package.

The original author's [English ONNX punctuation/casing model](https://huggingface.co/1-800-BAD-CODE/punctuation_fullstop_truecase_english) is one candidate: its model card describes punctuation and sentence-boundary restoration and declares Apache-2.0. [Horizon-Labs' small punctuation model](https://huggingface.co/Horizon-Labs/punctuation-restoration-small) is another ONNX-capable candidate. These are research options, not a claim that either has passed Sayward's acceptance corpus. Natural-language ambiguity still requires measurement; punctuation quality must not be represented as perfect.

## Proposed acceptance examples

| Input | Desired result |
| --- | --- |
| `i checked the log it finished successfully can you open the report` | `I checked the log. It finished successfully. Can you open the report?` |
| `the measurement is 3.14 on channel A1` | `The measurement is 3.14 on channel A1.` |
| `Can you open the report?` | `Can you open the report?` |
| Empty/filtered silence | No text or punctuation inserted |

These are acceptance targets, not observed model outputs. Include longer informal speech, contractions, proper nouns, code-like strings and multiple consecutive dictations in the corpus. Verify no duplicate punctuation, changed numbers, rewritten wording, accidental submission or loss of selected history after an error. Inspect actual clipboard/text-field results in both Windows and Mint VMs, including the packaged Windows installer.

## Approval

Andrew approved the fully local punctuation-only pass and the narrow separator rule, preserving his wording on both Windows and Linux. Cloud assistant integration and making the private GitHub repository public are separate decisions.
