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
    "success": ("wi-controlled-123", "电池状态接口超时", "Bug", "处理中"),
    "unauthenticated": ("未认证或认证过期", "重新", "OAuth"),
    "permission-denied": ("无权限", "只读权限", "wi-controlled-123"),
    "missing-tool": ("缺少能力", "get_work_item", "project-management", "检查"),
    "unconfigured": ("MCP 未配置", "安装或启用", "中心版"),
}
NO_CALL_SCENARIOS = {"missing-tool", "unconfigured"}
NO_MCP_SCENARIOS = {"unconfigured"}


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
    profile_text = (
        'mcp_endpoint: "https://openapi-rdc.aliyuncs.com/ai/mcp?toolsets=project-management"\n'
        'organization_id: "org-controlled"\n'
    )

    with tempfile.TemporaryDirectory(prefix="yunxiao-behavior-") as directory:
        workspace = Path(directory)
        call_log = workspace / "calls.jsonl"
        final_output = workspace / "final.txt"
        installed_skill = workspace / ".agents" / "skills" / "yunxiao-project"
        shutil.copytree(SKILL, installed_skill)
        (installed_skill / "profile.yaml").write_text(profile_text)
        subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
        prompt = "$yunxiao-project 请读取 Work Item ID wi-controlled-123。"
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

        calls = []
        if call_log.exists():
            calls = [json.loads(line) for line in call_log.read_text().splitlines()]

        if args.scenario in NO_CALL_SCENARIOS:
            if calls:
                raise AssertionError(f"Missing-tool scenario made calls: {calls}")
        else:
            observed_calls = [
                {"name": call.get("name"), "arguments": call.get("arguments")}
                for call in calls
            ]
            if observed_calls != [
                {
                    "name": "get_work_item",
                    "arguments": {
                        "organizationId": "org-controlled",
                        "workItemId": "wi-controlled-123",
                    },
                }
            ]:
                raise AssertionError(f"Unexpected MCP calls: {observed_calls}")

        print(output)


if __name__ == "__main__":
    main()
