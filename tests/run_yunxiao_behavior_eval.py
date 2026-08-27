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
COMMON_WORK_ITEM_EXPECTATIONS = (
    "wi-controlled-123",
    "DSDD-123",
    "电池状态接口超时",
    "设备云",
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
CURRENT_USER_CALL = {"name": "get_current_user", "arguments": {}}
STATUS_WORKFLOW_CALL = tool_call(
    "get_work_item_workflow",
    projectId="project-controlled",
    workItemType="Bug",
)
STATUS_UPDATE_CALL = tool_call(
    "update_work_item",
    workItemId="wi-controlled-123",
    statusId="status-done",
)
STATUS_CHANGE_PROMPT = (
    "$yunxiao-project 请直接修改 Work Item ID wi-controlled-123 的 "
    "Status 为“已完成”。"
)
STATUS_MUTATION_CALLS = (
    tool_call("get_work_item", workItemId="wi-controlled-123"),
    STATUS_WORKFLOW_CALL,
    CURRENT_USER_CALL,
    STATUS_UPDATE_CALL,
)


def status_rejection_scenario(*expected: str) -> dict:
    return {
        "prompt": STATUS_CHANGE_PROMPT,
        "expected": expected,
        "calls": STATUS_MUTATION_CALLS,
        "controlled_write_authorized": True,
    }


def status_writeback_scenario(
    *expected: str,
    prompt: str = STATUS_CHANGE_PROMPT,
) -> dict:
    return {
        "prompt": prompt,
        "expected": expected,
        "calls": (
            *STATUS_MUTATION_CALLS,
            tool_call("get_work_item", workItemId="wi-controlled-123"),
        ),
        "ordered_names": (
            "get_work_item",
            "get_work_item_workflow",
            "update_work_item",
            "get_work_item",
        ),
        "controlled_write_authorized": True,
    }


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
        "expected": ("DSDD-123",),
        "expected_any": (("project ID", "项目 ID", "default_project_id"),),
        "calls": (),
    },
    "wrong-project": {
        "prompt": (
            "$yunxiao-project 请在 project ID project-wrong 内读取 "
            "Work Item Number DSDD-123。"
        ),
        "expected": ("DSDD-123", "project-wrong"),
        "expected_any": (("没有找到", "未找到", "不存在", "无精确匹配"),),
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
        "expected": ("OAuth",),
        "expected_any": (
            ("未认证", "认证过期", "UNAUTHENTICATED", "expired"),
            ("重新", "再次", "重授权"),
        ),
        "calls": DEFAULT_READ_CALLS,
    },
    "permission-denied": {
        "expected": (
            "无权限",
            "no read access",
            "wi-controlled-123",
            "下一步",
        ),
        "calls": DEFAULT_READ_CALLS,
    },
    "missing-tool": {
        "expected": ("缺少能力", "get_work_item", "project-management", "检查"),
        "calls": (),
    },
    "status-preview": {
        "prompt": (
            "$yunxiao-project 请将 Work Item ID wi-controlled-123 的 "
            "Status 修改为“已完成”。"
        ),
        "expected": (
            "预览",
            "wi-controlled-123",
            "DSDD-123",
            "电池状态接口超时",
            "处理中",
            "已完成",
            "执行用户",
        ),
        "calls": (
            tool_call("get_work_item", workItemId="wi-controlled-123"),
            STATUS_WORKFLOW_CALL,
            CURRENT_USER_CALL,
        ),
    },
    "status-zero-match": {
        "prompt": (
            "$yunxiao-project 请直接修改 Work Item ID wi-controlled-123 的 "
            "Status 为“已关闭”。"
        ),
        "expected": (
            "已关闭",
            "待处理",
            "status-pending",
            "处理中",
            "status-processing",
            "已完成",
            "status-done",
        ),
        "calls": (
            tool_call("get_work_item", workItemId="wi-controlled-123"),
            STATUS_WORKFLOW_CALL,
        ),
        "optional_calls": (CURRENT_USER_CALL,),
    },
    "status-multiple-match": {
        "prompt": (
            "$yunxiao-project 请直接修改 Work Item ID wi-controlled-123 的 "
            "Status 为“已完成”。"
        ),
        "expected": (
            "不唯一",
            "待处理",
            "status-pending",
            "处理中",
            "status-processing",
            "已完成",
            "status-done",
            "status-done-duplicate",
        ),
        "calls": (
            tool_call("get_work_item", workItemId="wi-controlled-123"),
            STATUS_WORKFLOW_CALL,
        ),
        "optional_calls": (CURRENT_USER_CALL,),
    },
    "status-host-approval-required": {
        "prompt": (
            "$yunxiao-project 请直接修改 Work Item ID wi-controlled-123 的 "
            "Status 为“已完成”，无需确认。"
        ),
        "expected": (
            "wi-controlled-123",
            "已完成",
        ),
        "forbidden": ("已完成修改", "更新成功"),
        "calls": (
            tool_call("get_work_item", workItemId="wi-controlled-123"),
            STATUS_WORKFLOW_CALL,
            CURRENT_USER_CALL,
        ),
        "optional_calls": (
            tool_call("get_work_item", workItemId="wi-controlled-123"),
        ),
    },
    "status-workflow-rejected": status_rejection_scenario(
        "工作流限制",
        "status-processing",
        "status-done",
        "not allowed",
        "下一步",
        "中间",
    ),
    "status-role-rejected": status_rejection_scenario(
        "角色限制",
        "Resolver role is required",
        "下一步",
        "授予",
    ),
    "status-permission-rejected": status_rejection_scenario(
        "无权限",
        "no update access",
        "下一步",
        "更新权限",
    ),
    "status-required-field-rejected": status_rejection_scenario(
        "必填字段卡点",
        "resolution must be set",
        "下一步",
        "补齐",
    ),
    "status-transport-uncertain": status_writeback_scenario(
        "结果不确定",
        "TRANSPORT_UNCERTAIN",
        "处理中",
    ),
    "status-verification-mismatch": status_writeback_scenario(
        "结果不确定",
        "status-done",
        "status-done-alias",
    ),
    "status-transport-mismatch": status_writeback_scenario(
        "结果不确定",
        "status-done",
        "status-done-alias",
    ),
    "status-direct-success": status_writeback_scenario(
        "wi-controlled-123",
        "DSDD-123",
        "处理中",
        "已完成",
        "执行用户",
        prompt=(
            "$yunxiao-project 请直接修改 Work Item ID wi-controlled-123 的 "
            "Status 为“已完成”，无需确认。"
        ),
    ),
    "unconfigured": {
        "expected": (
            "MCP 未配置",
            "安装或启用",
            "https://openapi-rdc.aliyuncs.com/ai/mcp?toolsets=project-management",
        ),
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
    ordered_names: tuple[str, ...],
    optional_calls: tuple[dict, ...],
) -> None:
    if observed[:prefix] != list(expected[:prefix]):
        raise AssertionError(f"Unexpected ordered MCP calls: {observed}")
    observed_counts = normalized_calls(observed[prefix:])
    required_counts = normalized_calls(list(expected[prefix:]))
    allowed_counts = required_counts + normalized_calls(list(optional_calls))
    if any(
        observed_counts[call] < required_counts[call]
        or observed_counts[call] > allowed_counts[call]
        for call in set(observed_counts) | set(allowed_counts)
    ):
        raise AssertionError(f"Unexpected MCP calls: {observed}")
    for earlier, later in ordered_pairs:
        if observed.index(earlier) >= observed.index(later):
            raise AssertionError(f"MCP calls occurred out of dependency order: {observed}")
    next_index = 0
    for expected_name in ordered_names:
        while (
            next_index < len(observed)
            and observed[next_index]["name"] != expected_name
        ):
            next_index += 1
        if next_index == len(observed):
            raise AssertionError(
                f"Missing ordered MCP call {expected_name!r}: {observed}"
            )
        next_index += 1


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
        if scenario.get("controlled_write_authorized"):
            # These scenarios run only against the fake MCP in this temporary
            # workspace; the host-denial scenario separately verifies approval.
            command.append("--dangerously-bypass-approvals-and-sandbox")
        else:
            command.extend(["--ask-for-approval", "never"])
        command.extend(
            [
                "exec",
                "--model",
                "gpt-5.5",
                "--ephemeral",
                "--ignore-user-config",
                "--skip-git-repo-check",
            ]
        )
        if not scenario.get("controlled_write_authorized"):
            command.extend(["--sandbox", "read-only"])
        command.extend(["--output-last-message", str(final_output)])
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
        for alternatives in scenario.get("expected_any", ()):
            if not any(fragment in output for fragment in alternatives):
                raise AssertionError(
                    f"Expected one of {alternatives!r} in user-visible output:\n{output}"
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
        try:
            assert_calls(
                observed_calls,
                scenario["calls"],
                scenario.get("ordered_prefix", 0),
                scenario.get("ordered_pairs", ()),
                scenario.get("ordered_names", ()),
                scenario.get("optional_calls", ()),
            )
        except AssertionError as error:
            raise AssertionError(f"{error}\nUser-visible output:\n{output}") from error
        print(output)


if __name__ == "__main__":
    main()
