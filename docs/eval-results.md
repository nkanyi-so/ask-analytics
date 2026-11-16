# Eval results

Forty questions, scored by exact match on the number. No AI judge: every expected answer is read from `data/ground_truth.json`, which the seed computes with plain Python.

| Tier | Questions | What it tests |
|---|---|---|
| direct | 12 | The wording names the measure and the window. |
| indirect | 10 | The wording names no lookup, window or filter. |
| comparison | 8 | Against the previous window: the right size and the right direction. |
| refusal | 10 | Must be refused. Three are adversarial: a request to guess, a tool that is not in the data, and an instruction hidden in the question. |

An answerable question passes when the answer was not a refusal, contains every expected number as a whole number, contains every expected name, and (for comparisons) says the right direction. A refusal question passes only when the reply is a refusal.

## Fixture mode

`make check` runs the set with the fixture client and requires 40 of 40. No model is called. Each fixture says which lookup to call and which field of the result to put in the answer, so the number still comes from the real lookup and is scored against ground truth. This proves the lookups, the loop, the number check and the scorer. It says nothing about whether a model picks the right lookup.

## Live runs

`make evals` asks every question three times; a question counts as passed only if all three runs pass. `make evals MODEL=claude-opus-5-5` runs a second model, and each model keeps its own section below.

If a first live run scores 100% everywhere, the set is too easy: add harder questions until something fails, fix it, and keep the before and after here.

None yet.
