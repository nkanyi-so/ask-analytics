// Facts shown on the About view that the API does not serve. They are copied from
// docs/eval-results.md and must be updated when a new live run is recorded there.
export const REPO_URL = "https://github.com/nkanyi-so/ask-analytics";

export interface EvalRun {
  label: string;
  direct: string;
  indirect: string;
  comparison: string;
  refusal: string;
}

export const EVAL_RUNS: readonly EvalRun[] = [
  { label: "First live run, 16 Nov 2026", direct: "8 of 12", indirect: "9 of 10", comparison: "1 of 8", refusal: "10 of 10" },
  { label: "Latest live run, 17 Nov 2026", direct: "12 of 12", indirect: "10 of 10", comparison: "8 of 8", refusal: "10 of 10" },
];
