// The three questions offered under the Ask box. In demo mode these have recorded
// answers; backend/tests/test_frontend_contract.py keeps them in step with the eval set.
export const SUGGESTED_QUESTIONS: readonly string[] = [
  "How many invoices were issued in the last 7 days?",
  "Which tool is nobody touching?",
  "Did email usage go up or down this week, and by how much?",
];

// One the assistant should refuse: nothing in the data can answer it. Shown apart from
// the three above, so a visitor sees a refusal without having to stumble on one.
export const REFUSED_QUESTION = "What will usage look like next month?";
