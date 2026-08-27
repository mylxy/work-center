---
status: accepted
---

# Use a local mail CLI behind the skill

The email skill invokes a bundled Python 3.12 `mailctl` CLI instead of depending on a local MCP service, browser automation, or a globally installed command. This removes background-service and package-environment lifecycle management while keeping credentials out of prompts; the CLI uses the Python standard library plus a deliberately restricted Markdown renderer, exposes narrow subcommands, returns structured output, never accepts secrets in command arguments, and requires a Prepared Draft ID for every send.
