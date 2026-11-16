"""The tool catalog and its typed headline registry.

Every tool has exactly one headline event (its "golden metric"). The type checker
enforces that, in two ways:

- `catalog_entry` must handle every `ToolId`. Add an id without a case and
  `assert_never` fails the type check.
- `CatalogEntry.headline_event` is required and must be a known `HeadlineEvent`.
  Write a case without one, or with a made-up event, and the type check fails.

`tests/test_registry.py` proves both by running mypy on altered copies of this file.
"""

from dataclasses import dataclass
from typing import Literal, assert_never, get_args

ToolId = Literal[
    "call_agenda",
    "contact_enrichment",
    "email_drafter",
    "invoice_generator",
    "media_plan_builder",
    "meeting_notes",
    "proposal_writer",
    "report_summariser",
]

HeadlineEvent = Literal[
    "agenda_created",
    "contact_enriched",
    "email_sent",
    "invoice_issued",
    "plan_exported",
    "notes_filed",
    "proposal_sent",
    "summary_saved",
]


@dataclass(frozen=True)
class CatalogEntry:
    id: ToolId
    name: str
    headline_event: HeadlineEvent


def catalog_entry(tool: ToolId) -> CatalogEntry:
    match tool:
        case "call_agenda":
            return CatalogEntry(tool, "Call agenda", "agenda_created")
        case "contact_enrichment":
            return CatalogEntry(tool, "Contact enrichment", "contact_enriched")
        case "email_drafter":
            return CatalogEntry(tool, "Email drafter", "email_sent")
        case "invoice_generator":
            return CatalogEntry(tool, "Invoice generator", "invoice_issued")
        case "media_plan_builder":
            return CatalogEntry(tool, "Media plan builder", "plan_exported")
        case "meeting_notes":
            return CatalogEntry(tool, "Meeting notes", "notes_filed")
        case "proposal_writer":
            return CatalogEntry(tool, "Proposal writer", "proposal_sent")
        case "report_summariser":
            return CatalogEntry(tool, "Report summariser", "summary_saved")
        case _:
            assert_never(tool)


TOOL_IDS: tuple[ToolId, ...] = get_args(ToolId)
CATALOG: tuple[CatalogEntry, ...] = tuple(catalog_entry(tool) for tool in TOOL_IDS)
