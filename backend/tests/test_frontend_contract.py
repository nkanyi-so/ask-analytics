"""The frontend's TypeScript types are written by hand. These tests catch drift.

They compare field names only. Types are checked by `tsc` on one side and pydantic on
the other; what neither can see is a field renamed on one side and not the other.
"""

import re
from pathlib import Path

import pytest
from pydantic import BaseModel

from app.assistant import LookupCalled
from app.config import REPO_ROOT
from app.lookups import ClientActivity, ErrorGroup, PersonActivity, Roster, RosterPerson, ToolUsage
from app.main import AskResponse, HealthResponse, OverviewResponse, ReliabilityResponse
from evals import build

FRONTEND = REPO_ROOT / "frontend" / "src"
TYPES = (FRONTEND / "lib" / "types.ts").read_text()

MODELS: list[type[BaseModel]] = [
    ToolUsage,
    PersonActivity,
    ClientActivity,
    ErrorGroup,
    RosterPerson,
    Roster,
    OverviewResponse,
    ReliabilityResponse,
    LookupCalled,
    AskResponse,
    HealthResponse,
]


def interface_fields(name: str) -> set[str]:
    match = re.search(rf"export interface {name} \{{(.*?)\n\}}", TYPES, re.DOTALL)
    assert match, f"no `export interface {name}` in types.ts"
    return set(re.findall(r"^\s+(\w+)\??:", match.group(1), re.MULTILINE))


@pytest.mark.parametrize("model", MODELS, ids=[m.__name__ for m in MODELS])
def test_typescript_interface_has_the_same_fields_as_the_api_model(model: type[BaseModel]) -> None:
    assert interface_fields(model.__name__) == set(model.model_fields)


def test_suggested_questions_are_the_ones_with_recorded_answers() -> None:
    suggested = (FRONTEND / "lib" / "suggested.ts").read_text()

    for question in build.SUGGESTED:
        assert f'"{question}"' in suggested
    assert len(re.findall(r'^\s+"', suggested, re.MULTILINE)) == 3


def test_no_client_component_imports_the_server_only_backend_module() -> None:
    for path in FRONTEND.rglob("*.tsx"):
        source = path.read_text()
        if source.lstrip().startswith('"use client"'):
            assert "lib/backend" not in source, f"{path.name} would pull the token into the browser"
    assert 'import "server-only"' in (Path(FRONTEND) / "lib" / "backend.ts").read_text()
