#!/usr/bin/env python3
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from controlled_yunxiao_mcp import EXACT_COMMENT


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "yunxiao-project"
SERVER = Path(__file__).with_name("controlled_yunxiao_mcp.py")
DEFAULT_PROMPT = "$yunxiao-project 请读取 Work Item ID wi-controlled-123。"
COMMON_WORK_ITEM_EXPECTATIONS = (
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
)


def comment_expectations(first: int, last: int) -> tuple[str, ...]:
    return tuple(
        fragment
        for index in range(first, last + 1)
        for fragment in (
            f"评论用户{index}",
            f"2026-08-{19 + index:02d}T10:00:00Z",
            f"受控评论 {index}",
        )
    )


COMPACT_EXPECTATIONS = (*COMMON_WORK_ITEM_EXPECTATIONS, *comment_expectations(3, 7))
COMPACT_FORBIDDEN = (
    "受控评论 1",
    "受控评论 2",
    "待处理 → 处理中",
    "Normal → High",
)
FULL_EXPECTATIONS = (
    *COMMON_WORK_ITEM_EXPECTATIONS,
    "status-processing",
    "空字段",
    "报告用户",
    "2026-08-20T08:00:00Z",
    "2026-08-26T09:30:00Z",
    *comment_expectations(1, 7),
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
DIRECT_EXACT_COMMENT_PROMPT = (
    "$yunxiao-project 请对 Work Item ID wi-controlled-123 直接评论。"
    "评论原文仅位于 <comment> 与 </comment> 之间，标签不是正文："
    f"<comment>{EXACT_COMMENT}</comment>"
)
EXACT_COMMENT_CREATE_CALL = tool_call(
    "create_work_item_comment",
    workItemId="wi-controlled-123",
    content=EXACT_COMMENT,
)
EXACT_COMMENT_FAILURE_CALLS = (*DEFAULT_READ_CALLS, EXACT_COMMENT_CREATE_CALL)
EXACT_COMMENT_SUCCESS_CALLS = (
    *EXACT_COMMENT_FAILURE_CALLS,
    tool_call("list_work_item_comments", workItemId="wi-controlled-123"),
)
NUMBER_SEARCH_CALL = tool_call(
    "search_workitems",
    projectId="project-controlled",
    query="DSDD-123",
)
FIRST_COMMENTS_CALL = tool_call(
    "list_work_item_comments",
    workItemId="wi-controlled-123",
)
NEXT_COMMENTS_CALL = tool_call(
    "list_work_item_comments",
    workItemId="wi-controlled-123",
    cursor="comments-page-2",
)
SCENARIOS = {
    "success": {
        "expected": COMPACT_EXPECTATIONS,
        "forbidden": COMPACT_FORBIDDEN,
        "calls": DEFAULT_READ_CALLS,
    },
    "exact-comment": {
        "prompt": DIRECT_EXACT_COMMENT_PROMPT,
        "expected": (EXACT_COMMENT, "comment-created-1", "受控执行用户"),
        "calls": EXACT_COMMENT_SUCCESS_CALLS,
        "comment_write_sequence": True,
        "allow_controlled_write": True,
    },
    "intent-preview": {
        "prompt": (
            "$yunxiao-project 请为 Work Item ID wi-controlled-123 添加评论。"
            "评论意图：告知团队修复已合入 3.2.2，请回归电池状态接口并反馈结果。"
        ),
        "expected": (
            "wi-controlled-123",
            "DSDD-123",
            "评论草稿",
            "3.2.2",
            "电池状态接口",
            "反馈",
            "确认",
        ),
        "calls": (
            tool_call("get_work_item", workItemId="wi-controlled-123"),
        ),
    },
    "comment-transport-uncertain": {
        "prompt": DIRECT_EXACT_COMMENT_PROMPT,
        "expected": (
            "结果不确定",
            "connection closed",
            "不会自动",
            EXACT_COMMENT,
        ),
        "calls": EXACT_COMMENT_SUCCESS_CALLS,
        "comment_write_sequence": True,
        "allow_controlled_write": True,
    },
    "comment-transport-preexisting": {
        "prompt": DIRECT_EXACT_COMMENT_PROMPT,
        "expected": (
            "结果不确定",
            "comment-preexisting",
            "不会自动",
        ),
        "calls": EXACT_COMMENT_SUCCESS_CALLS,
        "comment_write_sequence": True,
        "allow_controlled_write": True,
    },
    "comment-business-error": {
        "prompt": DIRECT_EXACT_COMMENT_PROMPT,
        "expected": (
            "业务规则拒绝",
            "INVALID_ARGUMENT",
            "project text policy",
            "需要",
        ),
        "calls": EXACT_COMMENT_FAILURE_CALLS,
        "comment_write_sequence": True,
        "allow_controlled_write": True,
    },
    "comment-permission-denied": {
        "prompt": DIRECT_EXACT_COMMENT_PROMPT,
        "expected": ("无权限", "PERMISSION_DENIED", "当前 OAuth", "评论"),
        "calls": EXACT_COMMENT_FAILURE_CALLS,
        "comment_write_sequence": True,
        "allow_controlled_write": True,
    },
    "comment-unauthenticated": {
        "prompt": DIRECT_EXACT_COMMENT_PROMPT,
        "expected": ("未认证或认证过期", "重新", "OAuth"),
        "calls": EXACT_COMMENT_FAILURE_CALLS,
        "comment_write_sequence": True,
        "allow_controlled_write": True,
    },
    "comment-missing-tool": {
        "prompt": DIRECT_EXACT_COMMENT_PROMPT,
        "expected": (
            "缺少能力",
            "create_work_item_comment",
            "project-management",
        ),
        "calls": (),
    },
    "comment-approval-required": {
        "prompt": DIRECT_EXACT_COMMENT_PROMPT,
        "expected": ("写入未获批准", "MCP 写工具审批", "create_work_item_comment"),
        "calls": DEFAULT_READ_CALLS,
    },
    "direct-intent-comment": {
        "prompt": (
            "$yunxiao-project 请对 Work Item ID wi-controlled-123 直接评论。"
            "评论意图：告知团队修复已合入 3.2.2，请回归电池状态接口并反馈结果。"
        ),
        "expected": (
            "comment-created-1",
            "受控执行用户",
            "3.2.2",
            "电池状态接口",
            "反馈",
        ),
        "expected_call_names": (
            "get_work_item",
            "list_work_item_comments",
            "create_work_item_comment",
            "list_work_item_comments",
        ),
        "comment_content_fragments": ("3.2.2", "电池状态接口", "反馈"),
        "allow_controlled_write": True,
    },
    "top-level-only": {
        "prompt": (
            "$yunxiao-project 请回复 Work Item ID wi-controlled-123 的评论 "
            "comment-2，回复原文：已收到。"
        ),
        "expected": ("第一版", "顶层评论", "不支持", "回复"),
        "calls": (),
    },
    "existing-comment-mutations": {
        "prompt": (
            "$yunxiao-project 请编辑 Work Item ID wi-controlled-123 的评论 comment-1，"
            "删除 comment-2，并置顶 comment-3。"
        ),
        "expected": ("不支持", "编辑", "删除", "置顶"),
        "calls": (),
    },
    "multiple-comment-targets": {
        "prompt": (
            "$yunxiao-project 请对 Work Item ID wi-controlled-123 和 "
            "wi-controlled-456 直接评论，评论原文：统一回归。"
        ),
        "expected": ("单个", "两个目标", "没有调用写入"),
        "calls": (),
    },
    "comment-transport-confirmed": {
        "prompt": DIRECT_EXACT_COMMENT_PROMPT,
        "expected": (
            "结果不确定",
            "comment-created-1",
            "不会自动",
            EXACT_COMMENT,
        ),
        "calls": EXACT_COMMENT_SUCCESS_CALLS,
        "comment_write_sequence": True,
        "allow_controlled_write": True,
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
        "expected": ("DSDD-123", "没有找到", "project-wrong"),
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
            FIRST_COMMENTS_CALL,
            NEXT_COMMENTS_CALL,
            tool_call("list_workitem_activities", workItemId="wi-controlled-123"),
        ),
        "ordered_pairs": ((FIRST_COMMENTS_CALL, NEXT_COMMENTS_CALL),),
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


def assert_calls(
    observed: list[dict],
    expected: tuple[dict, ...],
    prefix: int,
    ordered_pairs: tuple[tuple[dict, dict], ...],
) -> None:
    if observed[:prefix] != list(expected[:prefix]):
        raise AssertionError(f"Unexpected ordered MCP calls: {observed}")
    if normalized_calls(observed[prefix:]) != normalized_calls(list(expected[prefix:])):
        raise AssertionError(f"Unexpected MCP calls: {observed}")
    for earlier, later in ordered_pairs:
        if observed.index(earlier) >= observed.index(later):
            raise AssertionError(f"MCP calls occurred out of dependency order: {observed}")


def assert_generated_comment_calls(
    observed: list[dict],
    expected_names: tuple[str, ...],
    content_fragments: tuple[str, ...],
) -> None:
    names = tuple(call["name"] for call in observed)
    if len(names) != 4:
        raise AssertionError(f"Unexpected MCP call count: {observed}")
    if Counter(names[:2]) != Counter(expected_names[:2]):
        raise AssertionError(f"Missing pre-write reads: {observed}")
    if names[2:] != expected_names[2:]:
        raise AssertionError(f"Unexpected MCP call order: {observed}")
    create_call = next(
        call for call in observed if call["name"] == "create_work_item_comment"
    )
    arguments = create_call["arguments"]
    if set(arguments) != {"organizationId", "workItemId", "content"}:
        raise AssertionError(f"Unexpected comment arguments: {arguments}")
    if arguments["organizationId"] != "org-controlled":
        raise AssertionError(f"Unexpected organization: {arguments}")
    if arguments["workItemId"] != "wi-controlled-123":
        raise AssertionError(f"Unexpected Work Item: {arguments}")
    for fragment in content_fragments:
        if fragment not in arguments["content"]:
            raise AssertionError(
                f"Expected {fragment!r} in generated comment: {arguments['content']!r}"
            )


def assert_comment_write_sequence(observed: list[dict]) -> None:
    names = [call["name"] for call in observed]
    if "create_work_item_comment" not in names:
        raise AssertionError(f"Comment creation was not attempted: {observed}")
    create_index = names.index("create_work_item_comment")
    if Counter(names[:create_index]) != Counter(
        ("get_work_item", "list_work_item_comments")
    ):
        raise AssertionError(f"Missing pre-write reads: {observed}")
    if names.count("create_work_item_comment") != 1:
        raise AssertionError(f"Comment creation was retried: {observed}")
    if names.count("list_work_item_comments") == 2:
        if names[-1] != "list_work_item_comments":
            raise AssertionError(f"Post-write verification was not last: {observed}")


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

        command = ["codex"]
        if not scenario.get("allow_controlled_write"):
            command.extend(["--ask-for-approval", "never"])
        command.extend(
            [
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
        )
        if scenario.get("allow_controlled_write"):
            command.append("--dangerously-bypass-approvals-and-sandbox")
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
        if "expected_call_names" in scenario:
            assert_generated_comment_calls(
                observed_calls,
                scenario["expected_call_names"],
                scenario["comment_content_fragments"],
            )
        else:
            assert_calls(
                observed_calls,
                scenario["calls"],
                scenario.get("ordered_prefix", 0),
                scenario.get("ordered_pairs", ()),
            )
            if scenario.get("comment_write_sequence"):
                assert_comment_write_sequence(observed_calls)
        print(output)


if __name__ == "__main__":
    main()
