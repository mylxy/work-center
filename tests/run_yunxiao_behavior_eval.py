#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "yunxiao-project"
SERVER = Path(__file__).with_name("controlled_yunxiao_mcp.py")
SCENARIO_EXPECTATIONS = {
    "success": (
        "wi-controlled-123",
        "电池状态接口超时",
        "Bug",
        "处理中",
        "影响版本",
        "3.2.1",
        "受控评论 3",
        "受控评论 7",
    ),
    "number-compact": (
        "DSDD-123",
        "wi-controlled-123",
        "电池状态接口超时",
        "受控评论 3",
        "受控评论 7",
    ),
    "url-compact": (
        "wi-controlled-123",
        "DSDD-123",
        "电池状态接口超时",
        "受控评论 7",
    ),
    "missing-project": ("配置不足", "project ID"),
    "wrong-project": ("DSDD-123", "精确匹配", "project-wrong"),
    "zero-match": ("DSDD-123", "没有找到", "OTHER-123"),
    "multiple-match": ("目标不唯一", "DSDD-123", "2"),
    "full-detail": (
        "wi-controlled-123",
        "DSDD-123",
        "报告用户",
        "2026-08-20T08:00:00Z",
        "2026-08-26T09:30:00Z",
        "受控评论 1",
        "受控评论 7",
        "待处理 → 处理中",
        "Normal → High",
    ),
    "unauthenticated": ("未认证或认证过期", "重新", "OAuth"),
    "permission-denied": ("无权限", "只读权限", "wi-controlled-123"),
    "missing-tool": ("缺少能力", "get_work_item", "project-management", "检查"),
    "unconfigured": ("MCP 未配置", "安装或启用", "中心版"),
}
SCENARIO_FORBIDDEN_OUTPUT = {
    scenario: (
        "受控评论 1",
        "受控评论 2",
        "待处理 → 处理中",
        "Normal → High",
    )
    for scenario in ("success", "number-compact", "url-compact")
}
NO_CALL_SCENARIOS = {"missing-tool", "unconfigured", "missing-project"}
NO_MCP_SCENARIOS = {"unconfigured"}
SEARCH_ONLY_SCENARIOS = {"wrong-project", "zero-match", "multiple-match"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        choices=tuple(SCENARIO_EXPECTATIONS),
        default="success",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    default_project_id = (
        None if args.scenario == "missing-project" else "project-controlled"
    )
    profile_text = (
        'mcp_endpoint: "https://openapi-rdc.aliyuncs.com/ai/mcp?toolsets=project-management"\n'
        'organization_id: "org-controlled"\n'
        f'default_project_id: {json.dumps(default_project_id)}\n'
    )

    with tempfile.TemporaryDirectory(prefix="yunxiao-behavior-") as directory:
        workspace = Path(directory)
        call_log = workspace / "calls.jsonl"
        final_output = workspace / "final.txt"
        installed_skill = workspace / ".agents" / "skills" / "yunxiao-project"
        shutil.copytree(SKILL, installed_skill)
        (installed_skill / "profile.yaml").write_text(profile_text)
        subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
        prompts = {
            "number-compact": "$yunxiao-project 请读取 Work Item Number DSDD-123。",
            "url-compact": (
                "$yunxiao-project 请读取 "
                "https://devops.aliyun.com/projex/organization/org-from-url/"
                "project/project-from-url/workitems?serialNumber=DSDD-123 的紧凑视图。"
            ),
            "missing-project": "$yunxiao-project 请读取 Work Item Number DSDD-123。",
            "wrong-project": (
                "$yunxiao-project 请在 project ID project-wrong 内读取 "
                "Work Item Number DSDD-123。"
            ),
            "zero-match": "$yunxiao-project 请读取 Work Item Number DSDD-123。",
            "multiple-match": "$yunxiao-project 请读取 Work Item Number DSDD-123。",
            "full-detail": (
                "$yunxiao-project 请读取 Work Item ID wi-controlled-123 的完整详情，"
                "包含全部字段、完整评论和最近活动。"
            ),
        }
        prompt = prompts.get(
            args.scenario,
            "$yunxiao-project 请读取 Work Item ID wi-controlled-123。",
        )
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
        if args.scenario not in NO_MCP_SCENARIOS:
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
        command.append(prompt)
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
        for fragment in SCENARIO_EXPECTATIONS[args.scenario]:
            if fragment not in output:
                raise AssertionError(
                    f"Expected {fragment!r} in user-visible output:\n{output}"
                )
        for fragment in SCENARIO_FORBIDDEN_OUTPUT.get(args.scenario, ()):
            if fragment in output:
                raise AssertionError(
                    f"Did not expect {fragment!r} in user-visible output:\n{output}"
                )

        calls = []
        if call_log.exists():
            calls = [json.loads(line) for line in call_log.read_text().splitlines()]

        if args.scenario in NO_CALL_SCENARIOS:
            if calls:
                raise AssertionError(f"Missing-tool scenario made calls: {calls}")
        elif args.scenario in SEARCH_ONLY_SCENARIOS:
            project_id = (
                "project-wrong"
                if args.scenario == "wrong-project"
                else "project-controlled"
            )
            observed_calls = [
                {"name": call.get("name"), "arguments": call.get("arguments")}
                for call in calls
            ]
            if observed_calls != [
                {
                    "name": "search_workitems",
                    "arguments": {
                        "organizationId": "org-controlled",
                        "projectId": project_id,
                        "query": "DSDD-123",
                    },
                }
            ]:
                raise AssertionError(f"Unexpected MCP calls: {observed_calls}")
        elif args.scenario == "number-compact":
            observed_calls = [
                {"name": call.get("name"), "arguments": call.get("arguments")}
                for call in calls
            ]
            if observed_calls != [
                {
                    "name": "search_workitems",
                    "arguments": {
                        "organizationId": "org-controlled",
                        "projectId": "project-controlled",
                        "query": "DSDD-123",
                    },
                },
                {
                    "name": "get_work_item",
                    "arguments": {
                        "organizationId": "org-controlled",
                        "workItemId": "wi-controlled-123",
                    },
                },
                {
                    "name": "list_work_item_comments",
                    "arguments": {
                        "organizationId": "org-controlled",
                        "workItemId": "wi-controlled-123",
                    },
                },
            ]:
                raise AssertionError(f"Unexpected MCP calls: {observed_calls}")
        elif args.scenario == "url-compact":
            observed_calls = [
                {"name": call.get("name"), "arguments": call.get("arguments")}
                for call in calls
            ]
            expected_calls = [
                {
                    "name": "search_workitems",
                    "arguments": {
                        "organizationId": "org-from-url",
                        "projectId": "project-from-url",
                        "query": "DSDD-123",
                    },
                },
                {
                    "name": "get_work_item",
                    "arguments": {
                        "organizationId": "org-from-url",
                        "workItemId": "wi-controlled-123",
                    },
                },
                {
                    "name": "list_work_item_comments",
                    "arguments": {
                        "organizationId": "org-from-url",
                        "workItemId": "wi-controlled-123",
                    },
                },
            ]
            by_name = lambda call: call["name"]
            if (
                not observed_calls
                or observed_calls[0] != expected_calls[0]
                or sorted(observed_calls[1:], key=by_name)
                != sorted(expected_calls[1:], key=by_name)
            ):
                raise AssertionError(f"Unexpected MCP calls: {observed_calls}")
        elif args.scenario == "full-detail":
            observed_calls = [
                {"name": call.get("name"), "arguments": call.get("arguments")}
                for call in calls
            ]
            expected_calls = [
                {
                    "name": "get_work_item",
                    "arguments": {
                        "organizationId": "org-controlled",
                        "workItemId": "wi-controlled-123",
                    },
                },
                {
                    "name": "list_work_item_comments",
                    "arguments": {
                        "organizationId": "org-controlled",
                        "workItemId": "wi-controlled-123",
                    },
                },
                {
                    "name": "list_workitem_activities",
                    "arguments": {
                        "organizationId": "org-controlled",
                        "workItemId": "wi-controlled-123",
                    },
                },
            ]
            by_name = lambda call: call["name"]
            if sorted(observed_calls, key=by_name) != sorted(expected_calls, key=by_name):
                raise AssertionError(f"Unexpected MCP calls: {observed_calls}")
        else:
            observed_calls = [
                {"name": call.get("name"), "arguments": call.get("arguments")}
                for call in calls
            ]
            expected_calls = [
                {
                    "name": "get_work_item",
                    "arguments": {
                        "organizationId": "org-controlled",
                        "workItemId": "wi-controlled-123",
                    },
                },
                {
                    "name": "list_work_item_comments",
                    "arguments": {
                        "organizationId": "org-controlled",
                        "workItemId": "wi-controlled-123",
                    },
                },
            ]
            by_name = lambda call: call["name"]
            if sorted(observed_calls, key=by_name) != sorted(expected_calls, key=by_name):
                raise AssertionError(f"Unexpected MCP calls: {observed_calls}")

        print(output)


if __name__ == "__main__":
    main()
