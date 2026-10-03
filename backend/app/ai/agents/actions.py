from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from uuid import uuid4

from langchain_core.messages import AIMessage

from app.ai.agents.state import AgentState
from app.db.base import SessionLocal, utcnow
from app.models.enums import TaskStatus
from app.models.maintenance import MaintenanceIssue
from app.models.tasks import Task
from app.models.workflows import WorkflowProposal


_UUID_PATTERN = (
    r"[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-"
    r"[0-9a-fA-F]{12}"
)

# Common tool result format:
#   "(pending, id=<uuid>)"
# Remove only the internal id fragment, preserving the useful row state and
# its surrounding punctuation.
_INTERNAL_ID_FIELD_RE = re.compile(
    r",?\s*\bid\s*[=:]\s*" + _UUID_PATTERN,
    re.IGNORECASE,
)

_INTERNAL_WITH_ID_RE = re.compile(
    r"\s+\bwith\s+id\s+" + _UUID_PATTERN,
    re.IGNORECASE,
)

_INTERNAL_BARE_UUID_RE = re.compile(
    _UUID_PATTERN,
    re.IGNORECASE,
)


_CLOUDINARY_DOWNLOAD_URL_RE = re.compile(
    r"https://api\.cloudinary\.com/[^\s]+",
    re.IGNORECASE,
)


def _sanitize_user_facing_result(value: object) -> str:
    """Hide internal identifiers and signed URLs in conversational text."""

    raw = str(value or "")

    # Preserve the real signed URL only in the structured API response.
    # Conversational text gets a stable placeholder instead.
    raw = _CLOUDINARY_DOWNLOAD_URL_RE.sub(
        "[secure document link available]",
        raw,
    )

    raw = _INTERNAL_ID_FIELD_RE.sub("", raw)
    raw = _INTERNAL_WITH_ID_RE.sub("", raw)
    raw = _INTERNAL_BARE_UUID_RE.sub("[internal-id]", raw)

    # Preserve list/newline structure returned by read tools. Only normalize
    # whitespace inside each individual line.
    lines = [
        " ".join(line.split())
        for line in raw.splitlines()
    ]

    return "\n".join(
        line
        for line in lines
        if line
    ).strip()




_MUTATION_HINTS = (
    "add ",
    "create ",
    "log ",
    "record ",
    "update ",
    "change ",
    "delete ",
    "remove ",
    "mark ",
    "complete ",
    "report ",
    "schedule ",
    "set ",
    "pay ",
    "assign ",
    "buy ",
)


_READ_TOOL_PREFIXES = ("get_", "list_", "search_")


def _is_read_tool(tool_name: object) -> bool:
    """Return True only for lookup/list tools that cannot mutate state."""

    name = str(tool_name or "").strip()
    return bool(name) and name.startswith(_READ_TOOL_PREFIXES)


def _action_requests_mutation(action: Dict) -> bool:
    """Detect whether the requested action changes household state.

    This intentionally ignores ``tool_name``. During entity resolution a
    mutation action can temporarily have ``tool_name=list_*`` or ``get_*``
    because the specialist first needs a server-derived identifier. A lookup
    must never make that mutation look completed.
    """

    text = " ".join(
        str(action.get(key) or "").casefold().strip()
        for key in ("intent", "description")
    )

    return any(hint in (text + " ") for hint in _MUTATION_HINTS)


def _action_requires_tool(action: Dict) -> bool:
    """Conservatively detect actions that must have a real tool outcome."""

    if action.get("tool_name"):
        return True

    return _action_requests_mutation(action)
_ERROR_RESULT_PREFIXES = (
    "that action failed:",
    "failed to ",
    "failed:",
    "error:",
    "unknown tool",
    "invalid ",
    "unable to ",
    "could not ",
    "couldn't ",
)


_READ_TOOL_ERROR_RESULTS = {
    "document retrieval is unavailable.",
    "document search is temporarily unavailable.",
    "document details are temporarily unavailable.",
    "the original document is temporarily unavailable.",
}


def _tool_result_is_error(
    tool_result: object,
    tool_name: object,
) -> bool:
    """Classify legacy string tool results conservatively.

    This is a compatibility layer until tools return structured
    success/error results.

    Empty read results such as "No tasks found." are valid read outcomes.
    Mutation failures such as "No task found with id ..." are failures.
    """

    normalized = " ".join(
        str(tool_result or "")
        .casefold()
        .split()
    ).strip()

    if not normalized:
        return False

    # ---------------------------------------------------------
    # Strong failure signatures for any tool
    # ---------------------------------------------------------
    if any(
        normalized.startswith(prefix)
        for prefix in _ERROR_RESULT_PREFIXES
    ):
        return True

    if "validationerror" in normalized:
        return True

    # ---------------------------------------------------------
    # Known infrastructure failures from read tools
    # ---------------------------------------------------------
    if normalized in _READ_TOOL_ERROR_RESULTS:
        return True

    # ---------------------------------------------------------
    # Read tools may legitimately return:
    #
    #   "No tasks found."
    #   "No approved documents matched that request."
    #
    # Those are successful empty reads, not execution failures.
    # ---------------------------------------------------------
    if _is_read_tool(tool_name):
        return False

    # ---------------------------------------------------------
    # Mutation-specific failure signatures
    # ---------------------------------------------------------

    # update/delete/complete of an entity that does not exist.
    if (
        normalized.startswith("no ")
        and " found" in normalized
    ):
        return True

    # Mutation was invoked but contained no actual change.
    if normalized == "no changes were provided.":
        return True

    # Validation-style mutation failures.
    if (
        normalized.startswith("missing ")
        or " is missing" in normalized
    ):
        return True

    if " must be " in normalized:
        return True

    return False

def _naturalize_description(value: object) -> str:
    """Turn a planner action description into a short completion sentence."""

    description = " ".join(str(value or "").split()).strip()
    if not description:
        return "Done."

    # Small household-language normalizations for common planner phrasing.
    description = re.sub(
        r"\bto grocery list\b",
        "to the grocery list",
        description,
        flags=re.IGNORECASE,
    )

    words = description.split(" ", 1)
    verb = words[0].casefold()
    rest = words[1] if len(words) > 1 else ""

    past_tense = {
        "add": "Added",
        "create": "Created",
        "log": "Logged",
        "record": "Recorded",
        "update": "Updated",
        "change": "Changed",
        "delete": "Deleted",
        "remove": "Removed",
        "mark": "Marked",
        "complete": "Completed",
        "report": "Reported",
        "schedule": "Scheduled",
        "set": "Set",
        "pay": "Paid",
        "assign": "Assigned",
        "find": "Found",
        "show": "Found",
        "retrieve": "Retrieved",
        "list": "Listed",
        "get": "Retrieved",
    }

    lead = past_tense.get(verb)
    if lead is None:
        sentence = description[0].upper() + description[1:]
    else:
        sentence = lead + ((" " + rest) if rest else "")

    if sentence[-1:] not in ".!?":
        sentence += "."

    return sentence


def _derive_display_result(
    action: Dict,
    raw_result: object,
    *,
    specialist_response: object = None,
) -> str:
    """Build a natural user-facing result while preserving raw tool output.

    The raw tool result remains in ``action["result"]`` for server-side
    chaining/audit. This function only produces presentation text.
    """

    specialist_text = _sanitize_user_facing_result(
        specialist_response
    ).strip()

    # For read/search tools, prefer the specialist's synthesis after it has
    # consumed the tool result. This avoids dumping raw document/DB payloads.
    if specialist_text:
        return specialist_text

    raw_text = str(raw_result or "")
    sanitized = _sanitize_user_facing_result(raw_result).strip()

    # Mutation tool results often append internal resource metadata such as
    # "Grocery item with id <uuid>". If an internal UUID was present, do not
    # try to repair the tool's storage-oriented string for presentation.
    # Use the planner's natural resource description instead.
    if (
        _action_requests_mutation(action)
        and _INTERNAL_BARE_UUID_RE.search(raw_text)
    ):
        return _naturalize_description(
            action.get("description")
        )

    # Special case original documents: the real signed URL is carried in the
    # structured API field, so the conversational response only needs a label.
    filename_match = re.search(
        r"(?im)^Original document:\s*(.+?)\s*$",
        str(raw_result or ""),
    )
    if filename_match:
        filename = " ".join(filename_match.group(1).split())
        base = _naturalize_description(action.get("description"))
        return "{0} You can open {1} below.".format(
            base.rstrip("."),
            filename,
        )

    # A bare UUID has no user meaning. If one survived only as an internal-id
    # placeholder, use the planner's resource description instead.
    if not sanitized or "[internal-id]" in sanitized:
        return _naturalize_description(action.get("description"))

    return sanitized


def _format_action_result(action: Dict) -> str:
    status = str(action.get("status") or "pending").strip().casefold()
    display_result = str(
        action.get("display_result")
        or _derive_display_result(
            action,
            action.get("result"),
        )
        or ""
    ).strip()
    if status == "needs_clarification":
        return display_result

    if status == "completed":
        return display_result or _naturalize_description(
            action.get("description")
        )

    if status == "unauthorized":
        reason = display_result or "You do not have permission for that."
        return "I couldn't complete that request: {0}".format(reason)

    if status == "failed":
        reason = display_result or "The requested action did not complete."
        return "I couldn't complete that request: {0}".format(reason)

    return "{0} ({1})".format(
        " ".join(str(action.get("description") or "Request").split()),
        status,
    )


def _build_final_response(actions: List[Dict]) -> str:
    if not actions:
        return "No actions were identified."

    rendered = [
        _format_action_result(action)
        for action in actions
    ]

    if len(rendered) == 1:
        return rendered[0]

    return "\n".join(
        "- {0}".format(item)
        for item in rendered
        if item
    ).strip()


def _finalize_approved_workflow(
    state: AgentState,
    action: Dict,
) -> bool:
    """Close the durable normal-chat proposal after its action finishes.

    Normal-chat confirmations persist one current action. Once that approved
    action has actually completed (or failed authorization/execution), its
    workflow row must not remain indefinitely in APPROVED state.
    """

    proposal_id = str(
        state.get("workflow_proposal_id") or ""
    ).strip()

    if not proposal_id:
        return False

    action_status = str(action.get("status") or "")
    if action_status not in {
        "completed",
        "failed",
        "unauthorized",
    }:
        return False

    session = SessionLocal()

    try:
        row = session.get(
            WorkflowProposal,
            proposal_id,
        )

        if row is None or row.status != "APPROVED":
            return False

        if action_status == "completed":
            row.status = "COMPLETED"
            row.last_error = None
        else:
            row.status = "FAILED"
            row.last_error = str(
                action.get("result")
                or "The approved action did not complete."
            )

        row.updated_at = utcnow()
        session.commit()
        return True

    except Exception:
        session.rollback()
        # The domain action result is already known. Do not rewrite it as a
        # success/failure based on audit-row cleanup. Codex will later move
        # normal-chat writes under the shared execution ledger.
        return False

    finally:
        session.close()



def _dependency_context(
    action: Dict[str, Any],
) -> Dict[str, Any]:
    value = action.get(
        "dependency_context"
    )

    if isinstance(value, dict):
        return dict(value)

    return {}


def _is_appliance_prerequisite(
    action: Dict[str, Any],
) -> bool:
    context = _dependency_context(
        action
    )

    return (
        str(
            context.get("kind")
            or ""
        ).strip()
        == "appliance_creation_prerequisite"
    )


def _created_appliance_id(
    tool_result: object,
) -> Optional[str]:
    """Extract only the server-generated id returned by add_appliance."""

    match = re.search(
        r"\bid\s*=\s*("
        + _UUID_PATTERN
        + r")",
        str(tool_result or ""),
        flags=re.IGNORECASE,
    )

    if match is None:
        return None

    return match.group(1)


def _prepared_parent_call(
    parent_action: Dict[str, Any],
    appliance_id: str,
) -> Optional[Dict[str, Any]]:
    context = _dependency_context(
        parent_action
    )

    if (
        str(
            context.get("kind")
            or ""
        ).strip()
        != "appliance_creation_parent"
    ):
        return None

    original_call = context.get(
        "original_tool_call"
    )

    if not isinstance(
        original_call,
        dict,
    ):
        return None

    tool_name = str(
        original_call.get("name")
        or ""
    ).strip()

    if tool_name not in {
        "log_repair",
        "report_issue",
        "create_task",
    }:
        return None

    args = dict(
        original_call.get("args")
        or {}
    )

    if tool_name in {
        "log_repair",
        "report_issue",
    }:
        args[
            "appliance_id"
        ] = appliance_id

    call_id = (
        "appliance-parent-resume-"
        + uuid4().hex
    )

    return {
        "name": tool_name,
        "args": args,
        "id": call_id,
    }


def _mark_parent_dependency_confirmed(
    parent_action: Dict[str, Any],
    appliance_id: str,
) -> Dict[str, Any]:
    updated = dict(
        parent_action
    )

    context = _dependency_context(
        updated
    )

    context.update(
        {
            "kind": (
                "appliance_creation_parent"
            ),
            "status": "confirmed",
            "confirmed_appliance_id": (
                appliance_id
            ),
        }
    )

    updated[
        "dependency_context"
    ] = context
    updated["status"] = "pending"
    updated["result"] = None
    updated["display_result"] = None

    return updated


def _cancel_parent_after_failed_prerequisite(
    parent_action: Dict[str, Any],
) -> Dict[str, Any]:
    updated = dict(
        parent_action
    )

    context = _dependency_context(
        updated
    )

    if (
        str(
            context.get("kind")
            or ""
        ).strip()
        != "appliance_creation_parent"
    ):
        return updated

    context["status"] = (
        "prerequisite_failed"
    )

    updated[
        "dependency_context"
    ] = context
    updated["status"] = "cancelled"
    updated["result"] = (
        "The original maintenance action was not attempted "
        "because the prerequisite appliance record was not created."
    )
    updated["display_result"] = (
        "The maintenance action was not attempted because "
        "the appliance record could not be created."
    )

    return updated

def _normalize_link_text(value: object) -> str:
    return " ".join(
        str(value or "").casefold().split()
    ).strip()


def _linked_followup_task_id(
    issue_id: str,
) -> Optional[str]:
    """Return one unambiguous active agent-style follow-up task for an issue.

    There is no task<->issue foreign key in the current schema. Until a future
    migration adds one, only the exact deterministic title generated by
    suggestions.py is eligible. Zero or multiple matches fail closed.
    """

    clean_issue_id = str(
        issue_id or ""
    ).strip()

    if not clean_issue_id:
        return None

    session = SessionLocal()

    try:
        issue = session.get(
            MaintenanceIssue,
            clean_issue_id,
        )

        if issue is None:
            return None

        description = " ".join(
            str(
                getattr(
                    issue,
                    "description",
                    "",
                )
                or ""
            ).split()
        ).strip()

        if not description:
            return None

        expected_title = _normalize_link_text(
            "Follow up: {0}".format(
                description
            )
        )

        rows = (
            session.query(Task)
            .filter(
                Task.status.in_(
                    [
                        TaskStatus.OPEN,
                        TaskStatus.IN_PROGRESS,
                    ]
                )
            )
            .all()
        )

        issue_created_at = getattr(
            issue,
            "created_at",
            None,
        )

        matches = []

        for task in rows:
            if (
                _normalize_link_text(
                    getattr(
                        task,
                        "title",
                        "",
                    )
                )
                != expected_title
            ):
                continue

            task_created_at = getattr(
                task,
                "created_at",
                None,
            )

            if (
                issue_created_at is not None
                and task_created_at is not None
            ):
                try:
                    issue_time = (
                        issue_created_at.replace(
                            tzinfo=None
                        )
                        if getattr(
                            issue_created_at,
                            "tzinfo",
                            None,
                        )
                        is not None
                        else issue_created_at
                    )
                    task_time = (
                        task_created_at.replace(
                            tzinfo=None
                        )
                        if getattr(
                            task_created_at,
                            "tzinfo",
                            None,
                        )
                        is not None
                        else task_created_at
                    )

                    if task_time < issue_time:
                        continue
                except (TypeError, ValueError):
                    # Timestamp comparison is only an additional safety signal.
                    # Exact title + uniqueness remains mandatory.
                    pass

            matches.append(
                task
            )

        if len(matches) != 1:
            return None

        return str(
            matches[0].task_id
        )

    finally:
        session.close()


def _internal_cascade_state_reset() -> Dict[str, Any]:
    """Clear durable-review state before running a server-derived cascade.

    The maintenance issue-close action may itself have come from a durable
    suggestion. Any follow-up complete_task call is a fresh deterministic
    internal action, not another suggestion revision.
    """

    return {
        "confirmation_kind": None,
        "confirmation_resolution": "none",
        "workflow_proposal_id": None,
        "editing_workflow_proposal_id": None,
        "pending_edit_context": None,
        "active_suggestion": None,
        "awaiting_confirmation": False,
        "force_action_review": False,
        "duplicate_status": None,
        "duplicate_details": None,
        "duplicate_match": None,
        "consistency_status": None,
        "consistency_results": [],
    }


def _maintenance_issue_close_cascade(
    action: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Prepare exact complete_task after a successfully closed issue."""

    if (
        str(
            action.get("status")
            or ""
        ).strip()
        != "completed"
    ):
        return None

    if (
        str(
            action.get("tool_name")
            or ""
        ).strip()
        != "update_issue"
    ):
        return None

    args = dict(
        action.get("tool_args")
        or {}
    )

    if (
        str(
            args.get("status")
            or ""
        ).strip().casefold()
        != "closed"
    ):
        return None

    issue_id = str(
        args.get("issue_id")
        or ""
    ).strip()

    task_id = _linked_followup_task_id(
        issue_id
    )

    if not task_id:
        return None

    chain_context = action.get(
        "suggestion_chain_context"
    )

    if isinstance(
        chain_context,
        dict,
    ):
        chain_context = dict(
            chain_context
        )
    else:
        chain_context = {}

    chain_context[
        "linked_followup_task_id"
    ] = task_id

    call_id = (
        "maintenance-followup-close-"
        + uuid4().hex
    )

    pending_tool_call = {
        "name": "complete_task",
        "args": {
            "task_id": task_id,
        },
        "id": call_id,
    }

    cascade_action: Dict[str, Any] = {
        "domain": "tasks",
        "intent": (
            "complete linked maintenance "
            "follow-up task"
        ),
        "description": (
            "Complete the follow-up task because "
            "the maintenance issue was closed."
        ),
        "tool_name": "complete_task",
        "tool_args": {
            "task_id": task_id,
        },
        "status": "pending",
        "result": None,
        "origin": (
            "maintenance_issue_close_cascade"
        ),
    }

    if chain_context:
        cascade_action[
            "suggestion_chain_context"
        ] = chain_context

    return {
        "action": cascade_action,
        "call": pending_tool_call,
        "chain_context": chain_context,
    }


def next_action_node(state: AgentState) -> dict:
    actions = state.get("planned_actions", [])
    index = state.get("current_action_index", 0)

    # ---------------------------------------------------------
    # No remaining action
    # ---------------------------------------------------------
    if index >= len(actions):
        return {
            "finished": True,
            "clarification_needed": False,
            "response": _build_final_response(actions),
        }

    current_action = dict(actions[index])

    # ---------------------------------------------------------
    # Clarification required
    #
    # IMPORTANT:
    # The action has NOT executed, so:
    # - do not advance current_action_index
    # - do not authorize
    # - do not execute
    # - do not mark failed
    # ---------------------------------------------------------
    if state.get("clarification_needed"):
        clarification = str(
            state.get("response")
            or "I need a little more information before I can do that."
        ).strip()

        current_action["status"] = "needs_clarification"
        current_action["result"] = clarification
        current_action["display_result"] = clarification

        updated_actions = list(actions)
        updated_actions[index] = current_action

        return {
            "planned_actions": updated_actions,

            # Keep the current action active.
            "current_action_index": index,

            "clarification_needed": True,

            "pending_tool_call": None,
            "pending_ai_message": None,
            "tool_result": None,

            "authorized": False,
            "auth_error": None,

            "finished": True,
            "response": clarification,
        }

    # ---------------------------------------------------------
    # Authorization failure
    # ---------------------------------------------------------
    if (
        state.get("authorized") is False
        and state.get("auth_error")
    ):
        auth_error = str(state["auth_error"])

        current_action["status"] = "unauthorized"
        current_action["result"] = auth_error
        current_action["display_result"] = (
            _sanitize_user_facing_result(auth_error)
        )

    # ---------------------------------------------------------
    # Tool result available
    # ---------------------------------------------------------
    elif state.get("tool_result") is not None:
        tool_result = str(state["tool_result"])

        executed_tool = str(
            current_action.get("tool_name") or ""
        ).strip()

        is_error_result = _tool_result_is_error(
            tool_result,
            executed_tool,
        )

        # -----------------------------------------------------
        # Tool explicitly failed
        # -----------------------------------------------------
        if is_error_result:
            current_action["status"] = "failed"
            current_action["result"] = tool_result
            current_action["display_result"] = (
                _derive_display_result(
                    current_action,
                    tool_result,
                )
            )

        # -----------------------------------------------------
        # Mutation requested but only a read tool ran
        #
        # Example:
        # update/delete action performs list/get first to
        # resolve an ID, but no mutation tool ever executes.
        # -----------------------------------------------------
        elif (
            _action_requests_mutation(current_action)
            and _is_read_tool(executed_tool)
        ):
            specialist_response = str(
                state.get("response") or ""
            ).strip()

            failure_result = (
                specialist_response
                or (
                    "The lookup completed, but no mutation tool "
                    "confirmed the requested change."
                )
            )

            current_action["status"] = "failed"
            current_action["result"] = failure_result
            current_action["display_result"] = (
                _derive_display_result(
                    current_action,
                    failure_result,
                    specialist_response=specialist_response,
                )
            )

        # -----------------------------------------------------
        # Successful tool execution
        # -----------------------------------------------------
        else:
            specialist_response = str(
                state.get("response") or ""
            ).strip()

            current_action["status"] = "completed"
            current_action["result"] = tool_result
            current_action["display_result"] = (
                _derive_display_result(
                    current_action,
                    tool_result,
                    specialist_response=(
                        specialist_response
                        if _is_read_tool(executed_tool)
                        else None
                    ),
                )
            )

    # ---------------------------------------------------------
    # Specialist returned text without executing a tool
    # ---------------------------------------------------------
    else:
        specialist_response = str(
            state.get("response") or ""
        ).strip()

        # A mutation cannot be considered successful without
        # an actual mutation tool result.
        if _action_requests_mutation(current_action):
            failure_result = (
                specialist_response
                or "No mutation tool confirmed the requested change."
            )

            current_action["status"] = "failed"
            current_action["result"] = failure_result
            current_action["display_result"] = (
                _derive_display_result(
                    current_action,
                    failure_result,
                    specialist_response=specialist_response,
                )
            )

        # Some actions require a tool even when they are not
        # detected by the generic mutation hints.
        elif _action_requires_tool(current_action):
            failure_result = (
                "No tool execution confirmed this requested action."
            )

            current_action["status"] = "failed"
            current_action["result"] = failure_result
            current_action["display_result"] = (
                _derive_display_result(
                    current_action,
                    failure_result,
                )
            )

        # Pure conversational/read-style answer that genuinely
        # does not require a tool.
        else:
            result = (
                specialist_response
                or "Action completed."
            )

            current_action["status"] = "completed"
            current_action["result"] = result
            current_action["display_result"] = (
                _derive_display_result(
                    current_action,
                    result,
                    specialist_response=result,
                )
            )

    # ---------------------------------------------------------
    # Store finalized action
    # ---------------------------------------------------------
    updated_actions = list(actions)
    updated_actions[index] = current_action

    # Close an approved durable workflow only after the action
    # has a real terminal outcome.
    proposal_finalized = _finalize_approved_workflow(
        state,
        current_action,
    )

    # ---------------------------------------------------------
    # Closed maintenance issue -> linked follow-up task cascade
    # ---------------------------------------------------------
    cascade = (
        _maintenance_issue_close_cascade(
            current_action
        )
    )

    if cascade is not None:
        cascade_action = dict(
            cascade["action"]
        )
        cascade_call = dict(
            cascade["call"]
        )

        cascade_index = len(
            updated_actions
        )

        updated_actions.append(
            cascade_action
        )

        pending_ai_message = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": (
                        cascade_call["name"]
                    ),
                    "args": dict(
                        cascade_call["args"]
                    ),
                    "id": (
                        cascade_call["id"]
                    ),
                    "type": "tool_call",
                }
            ],
        )

        result = {
            "planned_actions": (
                updated_actions
            ),
            "current_action_index": (
                cascade_index
            ),
            "clarification_needed": False,
            "clarification_context": None,
            "pending_tool_call": (
                cascade_call
            ),
            "pending_ai_message": (
                pending_ai_message
            ),
            "tool_result": None,
            "authorized": False,
            "auth_error": None,
            "finished": False,
            "response": "",
        }

        # The issue-close suggestion has finished. The linked task completion
        # is a fresh deterministic internal action and must not inherit the
        # previous suggestion's approval/routing state.
        result.update(
            _internal_cascade_state_reset()
        )

        return result

    # ---------------------------------------------------------
    # Appliance prerequisite -> exact parent action handoff
    # ---------------------------------------------------------
    if _is_appliance_prerequisite(
        current_action
    ):
        parent_index = index + 1

        if parent_index < len(
            updated_actions
        ):
            parent_action = dict(
                updated_actions[
                    parent_index
                ]
            )

            if (
                current_action.get(
                    "status"
                )
                == "completed"
            ):
                appliance_id = (
                    _created_appliance_id(
                        state.get(
                            "tool_result"
                        )
                    )
                )

                if appliance_id:
                    parent_action = (
                        _mark_parent_dependency_confirmed(
                            parent_action,
                            appliance_id,
                        )
                    )

                    prepared_call = (
                        _prepared_parent_call(
                            parent_action,
                            appliance_id,
                        )
                    )

                    if prepared_call:
                        updated_actions[
                            parent_index
                        ] = parent_action

                        pending_ai_message = (
                            AIMessage(
                                content="",
                                tool_calls=[
                                    {
                                        "name": (
                                            prepared_call[
                                                "name"
                                            ]
                                        ),
                                        "args": dict(
                                            prepared_call[
                                                "args"
                                            ]
                                        ),
                                        "id": (
                                            prepared_call[
                                                "id"
                                            ]
                                        ),
                                        "type": (
                                            "tool_call"
                                        ),
                                    }
                                ],
                            )
                        )

                        result = {
                            "planned_actions": (
                                updated_actions
                            ),
                            "current_action_index": (
                                parent_index
                            ),
                            "clarification_needed": (
                                False
                            ),
                            "clarification_context": (
                                None
                            ),
                            "pending_tool_call": (
                                prepared_call
                            ),
                            "pending_ai_message": (
                                pending_ai_message
                            ),
                            "tool_result": None,
                            "authorized": False,
                            "auth_error": None,
                            "finished": False,
                            "response": "",
                        }

                        if proposal_finalized:
                            result[
                                "workflow_proposal_id"
                            ] = None

                        return result

                # The appliance was inserted, but its returned id could not
                # be safely chained to the parent action.
                parent_action = dict(
                    parent_action
                )
                parent_action[
                    "status"
                ] = "failed"
                parent_action[
                    "result"
                ] = (
                    "The appliance record was created, but its "
                    "server-generated id could not be safely "
                    "carried into the original action."
                )
                parent_action[
                    "display_result"
                ] = (
                    "The appliance was added, but I couldn't safely "
                    "continue the original maintenance action."
                )

                updated_actions[
                    parent_index
                ] = parent_action

            else:
                updated_actions[
                    parent_index
                ] = (
                    _cancel_parent_after_failed_prerequisite(
                        parent_action
                    )
                )

        # Skip the parent action if the prerequisite failed or could not be
        # chained. Unrelated later actions may still continue.
        next_index = index + 2
    else:
        next_index = index + 1

    # ---------------------------------------------------------
    # All explicit actions finished
    # ---------------------------------------------------------
    if next_index >= len(updated_actions):
        result = {
            "planned_actions": updated_actions,
            "current_action_index": next_index,

            "clarification_needed": False,

            "pending_tool_call": None,
            "pending_ai_message": None,
            "tool_result": None,

            "authorized": False,
            "auth_error": None,

            "finished": True,
            "response": _build_final_response(
                updated_actions
            ),
        }

        if proposal_finalized:
            result["workflow_proposal_id"] = None

        return result

    # ---------------------------------------------------------
    # Move to next explicit action
    # ---------------------------------------------------------
    result = {
        "planned_actions": updated_actions,
        "current_action_index": next_index,

        # Any clarification belonged to the previous/current
        # action and must not leak into the next one.
        "clarification_needed": False,

        "pending_tool_call": None,
        "pending_ai_message": None,
        "tool_result": None,

        "authorized": False,
        "auth_error": None,

        "finished": False,
    }

    if proposal_finalized:
        result["workflow_proposal_id"] = None

    return result

def route_after_action(state: AgentState) -> str:
    if state.get("finished"):
        return "cross_domain_suggestion"

    # A dependency handoff can prepare the exact saved parent tool call
    # deterministically. Send it through the same clarification and
    # consistency gates without asking the LLM to regenerate it.
    if state.get("pending_tool_call"):
        return "clarification_gate"

    return "specialist"
