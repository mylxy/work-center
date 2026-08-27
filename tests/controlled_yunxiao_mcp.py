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
        choices=("success", "unauthenticated", "permission-denied", "missing-tool"),
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


def tool_result(scenario: str) -> dict:
    if scenario in ERROR_RESULTS:
        return ERROR_RESULTS[scenario]
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(WORK_ITEM, ensure_ascii=False),
            }
        ],
        "structuredContent": WORK_ITEM,
        "isError": False,
    }


def main() -> None:
    args = parse_args()
    log_path = Path(args.log)

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
                else [tool_definition()]
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
                    "result": tool_result(args.scenario),
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
