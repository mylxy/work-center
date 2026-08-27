#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys


WORK_ITEM = {
    "id": "wi-controlled-123",
    "serialNumber": "DSDD-123",
    "subject": "电池状态接口超时",
    "category": "Bug",
    "project": {"id": "project-controlled", "name": "设备云"},
    "status": {"id": "status-processing", "name": "处理中"},
    "priority": "High",
    "assignedTo": {"name": "测试用户"},
    "description": "设备偶发无法读取最新电池状态。",
    "customFields": [
        {"name": "影响版本", "value": "3.2.1"},
        {"name": "空字段", "value": None},
    ],
    "createdBy": {"name": "报告用户"},
    "createdAt": "2026-08-20T08:00:00Z",
    "updatedAt": "2026-08-26T09:30:00Z",
}
COMMENTS = [
    {
        "id": f"comment-{index}",
        "author": {"name": f"评论用户{index}"},
        "content": f"受控评论 {index}",
        "createdAt": f"2026-08-{19 + index:02d}T10:00:00Z",
    }
    for index in range(1, 8)
]
ACTIVITIES = [
    {
        "id": "activity-1",
        "action": "更新 Status",
        "detail": "待处理 → 处理中",
        "createdAt": "2026-08-26T09:30:00Z",
    },
    {
        "id": "activity-2",
        "action": "更新优先级",
        "detail": "Normal → High",
        "createdAt": "2026-08-25T09:00:00Z",
    },
]
WORKFLOW = {
    "statuses": [
        {"id": "status-pending", "name": "待处理"},
        {"id": "status-processing", "name": "处理中"},
        {"id": "status-done", "name": "已完成"},
    ]
}
CURRENT_USER = {
    "id": "user-controlled",
    "name": "执行用户",
    "organizationId": "org-controlled",
}
STATUS_UPDATE_ERRORS = {
    "status-workflow-rejected": (
        "WORKFLOW_RESTRICTION: transition from status-processing "
        "to status-done is not allowed"
    ),
    "status-role-rejected": "ROLE_RESTRICTION: Resolver role is required",
    "status-permission-rejected": (
        "PERMISSION_DENIED: no update access to this Work Item"
    ),
    "status-required-field-rejected": (
        "REQUIRED_FIELD: resolution must be set before this transition"
    ),
    "status-transport-uncertain": (
        "TRANSPORT_UNCERTAIN: connection dropped after request dispatch"
    ),
    "status-transport-mismatch": (
        "TRANSPORT_UNCERTAIN: connection dropped after request dispatch"
    ),
}
ERROR_RESULTS = {
    "unauthenticated": {
        "content": [
            {
                "type": "text",
                "text": "UNAUTHENTICATED: OAuth session expired",
            }
        ],
        "isError": True,
    },
    "permission-denied": {
        "content": [
            {
                "type": "text",
                "text": (
                    "PERMISSION_DENIED: no read access to Work Item "
                    "wi-controlled-123"
                ),
            }
        ],
        "isError": True,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True)
    parser.add_argument(
        "--scenario",
        choices=(
            "success",
            "number-compact",
            "url-compact",
            "missing-project",
            "wrong-project",
            "zero-match",
            "multiple-match",
            "full-detail",
            "unauthenticated",
            "permission-denied",
            "missing-tool",
            "status-preview",
            "status-zero-match",
            "status-multiple-match",
            "status-host-approval-required",
            "status-workflow-rejected",
            "status-role-rejected",
            "status-permission-rejected",
            "status-required-field-rejected",
            "status-transport-uncertain",
            "status-transport-mismatch",
            "status-verification-mismatch",
            "status-direct-success",
        ),
        default="success",
    )
    return parser.parse_args()


def send(message: dict) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def tool_definition() -> dict:
    return {
        "name": "get_work_item",
        "description": "Read one Yunxiao Work Item by opaque Work Item ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "organizationId": {"type": "string"},
                "workItemId": {"type": "string"},
            },
            "required": ["organizationId", "workItemId"],
            "additionalProperties": False,
        },
        "annotations": {
            "title": "Get Work Item",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    }


def identity_tool_definition() -> dict:
    return {
        "name": "get_current_user",
        "description": "Return the current OAuth identity.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "annotations": {
            "title": "Get Current User",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    }


def workflow_tool_definition() -> dict:
    return {
        "name": "get_work_item_workflow",
        "description": "Read the workflow for one Work Item project and type.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "organizationId": {"type": "string"},
                "projectId": {"type": "string"},
                "workItemType": {"type": "string"},
            },
            "required": ["organizationId", "projectId", "workItemType"],
            "additionalProperties": False,
        },
        "annotations": {
            "title": "Get Work Item Workflow",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    }


def search_tool_definition() -> dict:
    return {
        "name": "search_workitems",
        "description": "Search Work Items inside exactly one Yunxiao project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "organizationId": {"type": "string"},
                "projectId": {"type": "string"},
                "query": {"type": "string"},
            },
            "required": ["organizationId", "projectId", "query"],
            "additionalProperties": False,
        },
        "annotations": {
            "title": "Search Work Items",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    }


def comments_tool_definition() -> dict:
    return {
        "name": "list_work_item_comments",
        "description": "List one page of comments for a Work Item, oldest first.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "organizationId": {"type": "string"},
                "workItemId": {"type": "string"},
                "cursor": {"type": "string"},
            },
            "required": ["organizationId", "workItemId"],
            "additionalProperties": False,
        },
        "annotations": {
            "title": "List Work Item Comments",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    }


def activities_tool_definition() -> dict:
    return {
        "name": "list_workitem_activities",
        "description": "List recent activity for one Work Item, newest first.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "organizationId": {"type": "string"},
                "workItemId": {"type": "string"},
            },
            "required": ["organizationId", "workItemId"],
            "additionalProperties": False,
        },
        "annotations": {
            "title": "List Work Item Activities",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    }


def write_tool_definition(name: str, title: str) -> dict:
    return {
        "name": name,
        "description": "Controlled write trap; read-only scenarios must never call this.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "organizationId": {"type": "string"},
                "workItemId": {"type": "string"},
            },
            "required": ["organizationId", "workItemId"],
            "additionalProperties": True,
        },
        "annotations": {
            "title": title,
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    }


def update_tool_definition() -> dict:
    return {
        "name": "update_work_item",
        "description": "Update the Status of exactly one Work Item by Status ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "organizationId": {"type": "string"},
                "workItemId": {"type": "string"},
                "statusId": {"type": "string"},
            },
            "required": ["organizationId", "workItemId", "statusId"],
            "additionalProperties": False,
        },
        "annotations": {
            "title": "Update Work Item Status",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    }


def success_result(data: dict) -> dict:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(data, ensure_ascii=False),
            }
        ],
        "structuredContent": data,
        "isError": False,
    }


def error_result(message: str) -> dict:
    return {
        "content": [{"type": "text", "text": message}],
        "isError": True,
    }


def search_results(scenario: str) -> list[dict]:
    if scenario in {"wrong-project", "zero-match"}:
        return [
            {
                "id": "wi-near-123",
                "serialNumber": "OTHER-123",
                "subject": "非精确候选",
                "project": {"id": "project-controlled", "name": "设备云"},
            }
        ]
    if scenario == "multiple-match":
        return [
            {
                "id": "wi-controlled-123",
                "serialNumber": "DSDD-123",
                "subject": "电池状态接口超时",
                "project": {"id": "project-controlled", "name": "设备云"},
            },
            {
                "id": "wi-duplicate-123",
                "serialNumber": "DSDD-123",
                "subject": "重复编号受控数据",
                "project": {"id": "project-controlled", "name": "设备云"},
            },
        ]
    return [
        {
            "id": "wi-near-12",
            "serialNumber": "DSDD-12",
            "subject": "近似但不相同",
            "project": {"id": "project-controlled", "name": "设备云"},
        },
        {
            "id": "wi-controlled-123",
            "serialNumber": "DSDD-123",
            "subject": "电池状态接口超时",
            "project": {"id": "project-controlled", "name": "设备云"},
        },
    ]


def tool_result(
    scenario: str,
    name: str,
    arguments: dict,
    state: dict,
) -> dict:
    if name == "get_work_item" and scenario in ERROR_RESULTS:
        return ERROR_RESULTS[scenario]
    if name == "search_workitems":
        return success_result({"items": search_results(scenario)})
    if name == "list_work_item_comments":
        if scenario == "full-detail" and not arguments.get("cursor"):
            return success_result(
                {
                    "comments": COMMENTS[:4],
                    "nextCursor": "comments-page-2",
                }
            )
        if scenario == "full-detail" and arguments.get("cursor") == "comments-page-2":
            return success_result({"comments": COMMENTS[4:], "nextCursor": None})
        return success_result({"comments": COMMENTS})
    if name == "list_workitem_activities":
        return success_result({"activities": ACTIVITIES})
    if name == "get_current_user":
        return success_result(CURRENT_USER)
    if name == "get_work_item_workflow":
        if scenario == "status-multiple-match":
            return success_result(
                {
                    "statuses": [
                        *WORKFLOW["statuses"],
                        {"id": "status-done-duplicate", "name": "已完成"},
                    ]
                }
            )
        return success_result(WORKFLOW)
    if name == "update_work_item" and scenario in {
        "status-direct-success",
        "status-host-approval-required",
        "status-verification-mismatch",
    }:
        if arguments.get("statusId") != "status-done":
            return error_result("INVALID_STATUS_ID")
        state["status_updated"] = True
        return success_result({"id": WORK_ITEM["id"], "statusId": "status-done"})
    if name == "update_work_item" and scenario == "status-transport-mismatch":
        state["status_updated"] = True
    if name == "update_work_item" and scenario in STATUS_UPDATE_ERRORS:
        return error_result(STATUS_UPDATE_ERRORS[scenario])
    if name in {"update_work_item", "create_work_item_comment"}:
        return error_result("WRITE_TRAP_CALLED")
    work_item = dict(WORK_ITEM)
    if scenario in {
        "status-verification-mismatch",
        "status-transport-mismatch",
    } and state.get("status_updated"):
        work_item["status"] = {"id": "status-done-alias", "name": "已完成"}
    elif scenario in {
        "status-direct-success",
        "status-host-approval-required",
    } and state.get("status_updated"):
        work_item["status"] = {"id": "status-done", "name": "已完成"}
    return success_result(work_item)


def main() -> None:
    args = parse_args()
    log_path = Path(args.log)
    state = {"status_updated": False}

    for line in sys.stdin:
        message = json.loads(line)
        method = message.get("method")
        request_id = message.get("id")

        if method == "initialize":
            send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {
                            "name": "controlled-yunxiao",
                            "version": "1.0.0",
                        },
                    },
                }
            )
            continue

        if method == "tools/list":
            tools = (
                [identity_tool_definition()]
                if args.scenario == "missing-tool"
                else [
                    identity_tool_definition(),
                    tool_definition(),
                    search_tool_definition(),
                    comments_tool_definition(),
                    activities_tool_definition(),
                    workflow_tool_definition(),
                    update_tool_definition(),
                    write_tool_definition(
                        "create_work_item_comment",
                        "Create Work Item Comment",
                    ),
                ]
            )
            send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"tools": tools},
                }
            )
            continue

        if method == "tools/call":
            with log_path.open("a") as log_file:
                log_file.write(json.dumps(message["params"], ensure_ascii=False) + "\n")
            send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": tool_result(
                        args.scenario,
                        message["params"]["name"],
                        message["params"].get("arguments", {}),
                        state,
                    ),
                }
            )
            continue

        if request_id is not None:
            send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Unknown method: {method}"},
                }
            )


if __name__ == "__main__":
    main()
