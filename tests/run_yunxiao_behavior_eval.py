#!/usr/bin/env python3
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "yunxiao-project"
SERVER = Path(__file__).with_name("controlled_yunxiao_mcp.py")
DEFAULT_PROMPT = "$yunxiao-project 请读取 Work Item ID wi-controlled-123。"
COMPACT_EXPECTATIONS = (
    "wi-controlled-123",
    "DSDD-123",
    "电池状态接口超时",
    "设备云",
    "project-controlled",
    "Bug",
    "处理中",
    "High",
    "测试用户",
    "设备偶发无法读取最新电池状态。",
    "影响版本",
    "3.2.1",
    *(
        fragment
        for index in range(3, 8)
        for fragment in (
            f"评论用户{index}",
            f"2026-08-{19 + index:02d}T10:00:00Z",
            f"受控评论 {index}",
        )
    ),
)
COMPACT_FORBIDDEN = (
    "受控评论 1",
    "受控评论 2",
    "待处理 → 处理中",
    "Normal → High",
)
FULL_EXPECTATIONS = (
    "wi-controlled-123",
    "DSDD-123",
    "电池状态接口超时",
    "project-controlled",
    "设备云",
    "Bug",
    "status-processing",
    "处理中",
    "High",
    "测试用户",
    "设备偶发无法读取最新电池状态。",
    "影响版本",
    "3.2.1",
    "空字段",
    "报告用户",
    "2026-08-20T08:00:00Z",
    "2026-08-26T09:30:00Z",
    *(
        fragment
        for index in range(1, 8)
        for fragment in (
            f"评论用户{index}",
            f"2026-08-{19 + index:02d}T10:00:00Z",
            f"受控评论 {index}",
        )
    ),
    "更新 Status",
    "待处理 → 处理中",
    "更新优先级",
    "Normal → High",
)


def tool_call(name: str, organization_id: str = "org-controlled", **arguments) -> dict:
    return {
        "name": name,
        "arguments": {"organizationId": organization_id, **arguments},
    }


DEFAULT_READ_CALLS = (
    tool_call("get_work_item", workItemId="wi-controlled-123"),
    tool_call("list_work_item_comments", workItemId="wi-controlled-123"),
)
NUMBER_SEARCH_CALL = tool_call(
    "search_workitems",
    projectId="project-controlled",
    query="DSDD-123",
)
SCENARIOS = {
    "success": {
        "expected": COMPACT_EXPECTATIONS,
        "forbidden": COMPACT_FORBIDDEN,
        "calls": DEFAULT_READ_CALLS,
    },
    "number-compact": {
        "prompt": "$yunxiao-project 请读取 Work Item Number DSDD-123。",
        "expected": COMPACT_EXPECTATIONS,
        "forbidden": COMPACT_FORBIDDEN,
        "calls": (NUMBER_SEARCH_CALL, *DEFAULT_READ_CALLS),
        "ordered_prefix": 1,
    },
    "url-compact": {
        "prompt": (
            "$yunxiao-project 请读取 "
            "https://devops.aliyun.com/projex/organization/org-from-url/"
            "project/project-from-url/workitems?serialNumber=DSDD-123 的紧凑视图。"
        ),
        "expected": COMPACT_EXPECTATIONS,
        "forbidden": COMPACT_FORBIDDEN,
        "calls": (
            tool_call(
                "search_workitems",
                "org-from-url",
                projectId="project-from-url",
                query="DSDD-123",
            ),
            tool_call(
                "get_work_item",
                "org-from-url",
                workItemId="wi-controlled-123",
            ),
            tool_call(
                "list_work_item_comments",
                "org-from-url",
                workItemId="wi-controlled-123",
            ),
        ),
        "ordered_prefix": 1,
    },
    "missing-project": {
        "prompt": "$yunxiao-project 请读取 Work Item Number DSDD-123。",
        "default_project_id": None,
        "expected": ("配置不足", "project ID"),
        "calls": (),
    },
    "wrong-project": {
        "prompt": (
            "$yunxiao-project 请在 project ID project-wrong 内读取 "
            "Work Item Number DSDD-123。"
        ),
        "expected": ("DSDD-123", "精确匹配", "project-wrong"),
        "calls": (
            tool_call(
                "search_workitems",
                projectId="project-wrong",
                query="DSDD-123",
            ),
        ),
    },
    "zero-match": {
        "prompt": "$yunxiao-project 请读取 Work Item Number DSDD-123。",
        "expected": ("DSDD-123", "没有找到", "OTHER-123"),
        "calls": (NUMBER_SEARCH_CALL,),
    },
    "multiple-match": {
        "prompt": "$yunxiao-project 请读取 Work Item Number DSDD-123。",
        "expected": ("目标不唯一", "DSDD-123", "2"),
        "calls": (NUMBER_SEARCH_CALL,),
    },
    "full-detail": {
        "prompt": (
            "$yunxiao-project 请读取 Work Item ID wi-controlled-123 的完整详情，"
            "包含全部字段、完整评论和最近活动。"
        ),
        "expected": FULL_EXPECTATIONS,
        "calls": (
            tool_call("get_work_item", workItemId="wi-controlled-123"),
            tool_call("list_work_item_comments", workItemId="wi-controlled-123"),
            tool_call(
                "list_work_item_comments",
                workItemId="wi-controlled-123",
                cursor="comments-page-2",
            ),
            tool_call("list_workitem_activities", workItemId="wi-controlled-123"),
        ),
    },
    "unauthenticated": {
        "expected": ("未认证或认证过期", "重新", "OAuth"),
        "calls": DEFAULT_READ_CALLS,
    },
    "permission-denied": {
        "expected": ("无权限", "只读权限", "wi-controlled-123"),
        "calls": DEFAULT_READ_CALLS,
    },
    "missing-tool": {
        "expected": ("缺少能力", "get_work_item", "project-management", "检查"),
        "calls": (),
    },
    "unconfigured": {
        "expected": ("MCP 未配置", "安装或启用", "中心版"),
        "calls": (),
        "configure_mcp": False,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=tuple(SCENARIOS), default="success")
    return parser.parse_args()


def normalized_calls(calls: list[dict]) -> Counter:
    return Counter(json.dumps(call, ensure_ascii=False, sort_keys=True) for call in calls)


def assert_calls(observed: list[dict], expected: tuple[dict, ...], prefix: int) -> None:
    if observed[:prefix] != list(expected[:prefix]):
        raise AssertionError(f"Unexpected ordered MCP calls: {observed}")
    if normalized_calls(observed[prefix:]) != normalized_calls(list(expected[prefix:])):
        raise AssertionError(f"Unexpected MCP calls: {observed}")


def main() -> None:
    args = parse_args()
    scenario = SCENARIOS[args.scenario]
    profile_text = (
        'mcp_endpoint: "https://openapi-rdc.aliyuncs.com/ai/mcp?toolsets=project-management"\n'
        'organization_id: "org-controlled"\n'
        f'default_project_id: {json.dumps(scenario.get("default_project_id", "project-controlled"))}\n'
    )

    with tempfile.TemporaryDirectory(prefix="yunxiao-behavior-") as directory:
        workspace = Path(directory)
        call_log = workspace / "calls.jsonl"
        final_output = workspace / "final.txt"
        installed_skill = workspace / ".agents" / "skills" / "yunxiao-project"
        shutil.copytree(SKILL, installed_skill)
        (installed_skill / "profile.yaml").write_text(profile_text)
        subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)

        command = [
            "codex",
            "--ask-for-approval",
            "never",
            "exec",
            "--model",
            "gpt-5.5",
            "--ephemeral",
            "--ignore-user-config",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--output-last-message",
            str(final_output),
        ]
        if scenario.get("configure_mcp", True):
            command.extend(
                [
                    "-c",
                    f'mcp_servers.yunxiao.command="{Path("/usr/bin/python3")}"',
                    "-c",
                    (
                        "mcp_servers.yunxiao.args="
                        + json.dumps(
                            [
                                str(SERVER),
                                "--log",
                                str(call_log),
                                "--scenario",
                                args.scenario,
                            ]
                        )
                    ),
                ]
            )
        command.append(scenario.get("prompt", DEFAULT_PROMPT))
        completed = subprocess.run(
            command,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if completed.returncode != 0:
            raise AssertionError(
                f"Codex eval failed ({completed.returncode}):\n{completed.stderr}"
            )

        output = final_output.read_text()
        for fragment in scenario["expected"]:
            if fragment not in output:
                raise AssertionError(
                    f"Expected {fragment!r} in user-visible output:\n{output}"
                )
        for fragment in scenario.get("forbidden", ()):
            if fragment in output:
                raise AssertionError(
                    f"Did not expect {fragment!r} in user-visible output:\n{output}"
                )

        calls = []
        if call_log.exists():
            calls = [json.loads(line) for line in call_log.read_text().splitlines()]
        observed_calls = [
            {"name": call.get("name"), "arguments": call.get("arguments")}
            for call in calls
        ]
        assert_calls(
            observed_calls,
            scenario["calls"],
            scenario.get("ordered_prefix", 0),
        )
        print(output)


if __name__ == "__main__":
    main()
