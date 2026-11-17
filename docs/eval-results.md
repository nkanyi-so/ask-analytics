# Eval results

Forty questions, scored by exact match on the number. No AI judge: every expected answer is read from `data/ground_truth.json`, which the seed computes with plain Python.

| Tier | Questions | What it tests |
|---|---|---|
| direct | 12 | The wording names the measure and the window. |
| indirect | 10 | The wording names no lookup, window or filter. |
| comparison | 8 | Against the previous window: the right size and the right direction. |
| refusal | 10 | Must be refused. Three are adversarial: a request to guess, a tool that is not in the data, and an instruction hidden in the question. |

An answerable question passes when the answer was not a refusal, contains every expected number as a whole number, contains every expected name, and (for comparisons) says the right direction. A refusal question passes only when the reply is a refusal.

Three things to keep in mind when reading a table:

- Dates and window phrases ("30 October 2026", "the last 7 days") are removed from an answer before its numbers are matched, so they cannot satisfy an expected number by accident. For comparisons, the direction word has to be near the number, and the opposite word must not be.
- A few expected numbers are small (1, 3, 5). An answer could contain one for another reason, so a pass on those questions is weaker evidence than a pass on 382.
- "Who has gone quiet?" expects the 7-day answer (two people), because the assistant is told to use 7 days when no window is named. Over 30 days the right answer is one person. A failure there measures the choice of window, not the count.

## Fixture mode

`make check` runs the set with the fixture client and requires 40 of 40. No model is called. Each fixture says which lookup to call and which field of the result to put in the answer, so the number still comes from the real lookup and is scored against ground truth. This proves the lookups, the loop, the number check and the scorer. It says nothing about whether a model picks the right lookup.

## Live runs

`make evals` asks every question three times; a question counts as passed only if all three runs pass. `make evals MODEL=claude-opus-5-5` runs a second model, and each model keeps its own section below.

If a first live run scores 100% everywhere, the set is too easy: add harder questions until something fails, fix it, and keep the before and after here.

<!-- begin:claude-haiku-5-5 -->
### `claude-haiku-5-5`

Run on 17 Nov 2026, 11:50 UTC. 40 questions, 3 runs each. Cost: $0.0765.

| Tier | Questions | Passed all 3 runs | Rate | Single runs passed |
|---|---|---|---|---|
| direct | 12 | 12 | 100% | 36 of 36 |
| indirect | 10 | 10 | 100% | 30 of 30 |
| comparison | 8 | 8 | 100% | 24 of 24 |
| refusal | 10 | 10 | 100% | 30 of 30 |
| all | 40 | 40 | 100% | 120 of 120 |

Failures (any run):

None.
<!-- end:claude-haiku-5-5 -->

## How `claude-haiku-5-5` got from 70% to 100%

The table above is the eighth live run. The earlier ones are kept here, because the failures are the useful part. Each run asked all 40 questions three times; "passed" means right on all three.

**Read the 100% with care.** The fixes below were made while looking at this same set of questions, so the last run is partly fitted to it. It shows that every failure found was understood and fixed. It does not show how the assistant does on questions it has not seen. The next step is a second set of questions, written before looking at any answers and never used for tuning.

| Run (16 Nov 2026) | Direct | Indirect | Comparison | Refusal | All | Single runs | Cost |
|---|---|---|---|---|---|---|---|
| 0 | every request rejected | | | | | 0 of 120 | $0.00 |
| 1, 17:27 UTC | 8 of 12 | 9 of 10 | 1 of 8 | 10 of 10 | 28 of 40 (70%) | 95 of 120 | $0.065 |
| 2, 17:37 UTC | 11 of 12 | 9 of 10 | 7 of 8 | 10 of 10 | 37 of 40 (92%) | 114 of 120 | $0.069 |
| 3, 17:45 UTC | 11 of 12 | 10 of 10 | 5 of 8 | 10 of 10 | 36 of 40 (90%) | 114 of 120 | $0.074 |
| 4, 17:52 UTC | 12 of 12 | 10 of 10 | 8 of 8 | 10 of 10 | 40 of 40 (100%) | 120 of 120 | $0.074 |
| 5, 18:06 UTC | 12 of 12 | 10 of 10 | 8 of 8 | 10 of 10 | 40 of 40 (100%) | 120 of 120 | $0.075 |
| 6, 17 Nov | 12 of 12 | 9 of 10 | 6 of 8 | 10 of 10 | 37 of 40 (92%) | 116 of 120 | $0.076 |
| 7, 17 Nov | 12 of 12 | 10 of 10 | 8 of 8 | 10 of 10 | 40 of 40 (100%) | 120 of 120 | $0.077 |
| 8, 17 Nov | 12 of 12 | 10 of 10 | 8 of 8 | 10 of 10 | 40 of 40 (100%) | 120 of 120 | $0.077 |

The scorer changed between runs (see below), so the rows are each scored as they were at the time and are not strictly comparable. Run 4 was scored by a scorer that a review then found too lenient, and run 7 with a number check that a review found too loose; runs 5 and 8 are the ones to trust. Which refusals came from the model and which from the number check is taken from that day's logs, since both produce the same refusal text. The refusal tier was 30 of 30 in every run, before and after every change.

### Run 0: every call rejected

The API refused all 120 requests with a 400: the `errors_seen` tool declared its optional `tool_id` as an enum whose type was `["string", "null"]`, which strict tool schemas do not accept. No question was answered and nothing was billed. Fixture evals could not have caught this, because the fixture client never sends a schema anywhere. *Fix:* `anyOf` of a string enum and null. The API's own error message is now logged when a call fails.

### Run 1: 70%

Twelve questions failed. The causes, with the answer that showed each one:

- **The number check stopped the model doing arithmetic.** Asked "Are people actually logging in?", the model fetched every person and counted them itself: "35 of the 40 people logged in". The count was right. The check refused it anyway, because 35 and 40 were not numbers in that tool result. This is the rule working as designed. *Fix:* the prompt now says never to count rows and that the roster carries the counts.
- **The model worked out a date.** "122 outputs in the last 7 days (7d window, 2026-10-24 to 2026-10-30)": the start date was not in any result, so the check refused a correct answer. *Fix:* every tool result now states the first and last day of its window, and of the previous window when asked, so the model copies them.
- **Numbers written as words.** "Ten invoices were issued" has no 10 in it. *Fix in this run:* a firmer prompt. That was not enough; see run 3.
- **A total asked for, a breakdown given.** For "are errors on the invoice generator up or down, and by how much?" the model used `errors_seen` and reported +86 for one source and -2 for another, and rightly declined to net them. The total (+84) is in `usage_by_tool`. *Fix:* the tool descriptions now say which one holds a tool's total.
- **Two scorer mistakes.** "a rise of 5" failed because the scorer did not know the word "rise", and "a change of -41" failed because it ignored the sign. Both answers were correct. *Fix:* the word, and a signed number now counts as a direction.

### Run 2: 92%

- **The model refused "How many emails were sent in the last 30 days?"** two times out of three, then six times out of six when asked again. The prompt said there were eight tools and never named them, so the model could not tell that emails were something a tool counts. *Fix:* the prompt now lists the eight tools and what each one counts, generated from the typed registry. After that: six right out of six, and "the last 90 days" and "revenue" still refused.
- **"compared with the previous 30"** was refused three times out of three: a window named without the word "days" looked like an invented number. *Fix, as first made:* the check accepted "last/previous 7" and "30" when no word followed. That was too loose; see run 4.
- **A numbered list** ("1. Yara Dunmore") put a 1 in the answer that no result justified. *Fix:* the prompt asks for dashes.

### Run 3: 90%

All four failures were correct answers.

- **"Three people were invited but have never logged in"**, three times out of three, after two rounds of telling the model to use digits. The lesson is that the prompt does not control this. And it matters beyond scoring: a number written as a word passed the number check unchecked, which ARCHITECTURE had listed as a known hole. *Fix:* the check now reads number words and holds them to the same rule as digits. "One" is left out, because "no one" and "the one tool" are not counts.
- **Direction read from too wide a window.** "That is an increase of 84. Invoices issued fell over the same period" failed because "fell" was within six words of 84. *Fix:* direction is read from the sentence or clause that holds the number, and a signed number settles it outright.

### Run 4: 100%, and a review that did not accept it

No failures. But a fresh review of the changes made since run 1 found that two of them had gone too far. Both would have let a wrong answer through, and neither was caught by a test:

- **The window allowance was a way round the number check.** "86 errors, up from the previous 7" passed, with no 7 in any result. That is exactly where an invented previous value would sit. *Fix:* a window may be named without "days" only as the thing compared with ("compared with the previous 30"), and only for a window that turn really compared.
- **The scorer let a sign overrule a word.** "Invoices rose by 41, errors -41" scored as "down 41". *Fix:* a sign counts as one more direction word, so it can supply a direction and it can contradict one. Direction is also read only from words within eight of the number and inside its own clause, not the whole sentence.
- **Number words in the scorer could match by accident** ("all three windows" for an expected 3), and tied the scorer to the code it scores. *Fix:* the scorer reads digits only again and shares no code with the check. Instead, once an answer has passed the number check, the assistant rewrites its number words as digits, so "Three people" reaches the reader, and the scorer, as "3 people".
- "Twenty-two" was read as a 20 and a 2. It is now one number, and words such as "hundred" are never accepted.

### Run 5: 100%

No failures, with the stricter check and scorer. Total spent across all five runs and the single test calls in between: about $0.38.

### Run 6: 92%, after a change to the wording

On 17 Nov the prompt was changed for readers, not for the score: the model was told to write a date as "24 October 2026" and a time range as "the last 7 days", and to say what a tool counts in plain words. The eval was rerun because the prompt had changed, and it fell to 92%. All four failing runs were correct answers refused by the number check:

- **A span of days written once.** "against 51 in the previous 7 days (17 to 23 October 2026)" left a bare 17 with no month after it, which the check read as an invented number. *Fix:* a span of days in one month is read as a date when both ends are dates in the results. "18 to 23 October" is still refused, because the 18th is not.
- **A number from the instructions, not from a lookup.** "outputs from all eight tools combined": the prompt told the model the workspace has eight tools, and it repeated that. The check refused it, correctly, because no lookup result said so. *Fix:* the prompt no longer states how many tools or people there are, and tells the model to say nothing about the workspace that a result did not.

### Run 7: 100%, and the same mistake caught again in review

No failures. But the span fix as first written accepted any two dates in a result as a span, so in an answer about people "28 – 30 October" would have passed with no 28 in the result. That is the run 4 mistake again: a check loosened too far to cure a false refusal. *Fix:* only a window's own first and last day, as the result gives them, make a span. Run 8 below was scored with the narrower rule.

### Run 8: 100%

No failures, with the narrower span rule. This is the run in the table at the top. Runs 6, 7 and 8 cost about $0.23 together.

The lesson of run 6 is the reason the eval exists: a change that looked like copy-editing broke answers, and nothing else would have shown it.

### What this says about the design

- The refusal behaviour never failed, including the three adversarial questions, in 120 refusal runs.
- The number check did its job on live answers: it stopped a count the model made itself and a date it derived, and since run 3 it also stops a spelled-out number that no result supports.
- Loosening a check to fix a false refusal is where the risk is. Both mistakes found by the review came from doing that, and both looked reasonable when made.
- Most of what looked like model failure was missing information: the model was not told which tools exist, which lookup holds a total, or what days a window covers. Each fix gave it the fact rather than a firmer instruction. The one firmer instruction that was tried (use digits) did not work.
