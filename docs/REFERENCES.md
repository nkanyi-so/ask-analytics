# References

Started from `../ytscribe/docs/REFERENCES.md`. Kept what applies to a small FastAPI service with a model in the loop; dropped the yt-dlp, transcript and CLI entries.

## Exemplary public repos (what to borrow, not copy)
- **cosmicpython/code** (https://github.com/cosmicpython/code): example code for *Architecture Patterns with Python*. Borrow: one port with swappable adapters (our `EventSource` and `ModelClient`), and fakes instead of mocks in tests (the fixture client).
- **simonw/llm** (https://github.com/simonw/llm): a CLI that reaches many model providers through plugins and logs every prompt and response. Borrow: one interface with swappable providers, and a per-call log of latency, tokens and cost.
- **humanlayer/12-factor-agents** (https://github.com/humanlayer/12-factor-agents): principles for LLM software that holds up in production. Borrow: tools are structured outputs, code stays in control of the flow, the model only routes and words.
- **fastapi/full-stack-fastapi-template** (https://github.com/fastapi/full-stack-fastapi-template): production project hygiene for FastAPI. Borrow: typed settings from the environment, test layout and CI shape. Skip its Postgres, Docker and React.

## Official docs this repo follows
- **Anthropic tool use** (https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview): borrow the manual loop: send tools, run each `tool_use` block, return every `tool_result` in one user message, stop on `end_turn`, and check `stop_reason` (including `refusal`) before reading content. Strict tool schemas keep arguments valid.
- **Anthropic models and pricing** (https://platform.claude.com/docs/en/about-claude/models/overview and https://platform.claude.com/docs/en/about-claude/pricing): the model ids and per-token prices behind the cost log and the daily budget.
- **FastAPI, bigger applications** (https://fastapi.tiangolo.com/tutorial/bigger-applications/) and **settings** (https://fastapi.tiangolo.com/advanced/settings/): borrow one `app/` package, an app factory, dependencies for auth, and settings read once from the environment with pydantic-settings.
- **Next.js app router** (https://nextjs.org/docs/app, and the copy shipped in `frontend/node_modules/next/dist/docs/`): borrow server components for reads and route handlers for the one write, so the admin token stays on the server.

## Libraries (check current docs before use; APIs change)
- uv: https://docs.astral.sh/uv/
- FastAPI: https://fastapi.tiangolo.com/
- SQLAlchemy Core: https://docs.sqlalchemy.org/en/21/core/
- pydantic-settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- Anthropic Python SDK: https://github.com/anthropics/anthropic-sdk-python
- Mixpanel import API: https://docs.mixpanel.com/reference/import-events · raw export API: https://docs.mixpanel.com/reference/raw-event-export · service accounts: https://docs.mixpanel.com/reference/service-accounts
- MCP Python SDK (2.x): https://py.sdk.modelcontextprotocol.io/ · Claude Desktop config: https://modelcontextprotocol.io/docs/develop/connect-local-servers
- mypy: https://mypy.readthedocs.io/ · ruff: https://docs.astral.sh/ruff/
- Vitest: https://vitest.dev/
- gitleaks: https://github.com/gitleaks/gitleaks

## Claude Code practices this repo follows
- Best practices: https://code.claude.com/docs/en/best-practices
- Permission modes (plan, auto): https://code.claude.com/docs/en/permission-modes
- Hooks: https://code.claude.com/docs/en/hooks-guide
- Subagents: https://code.claude.com/docs/en/sub-agents · Skills: https://code.claude.com/docs/en/skills
