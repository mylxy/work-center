---
name: log-iot-hub-v2
description: Query fixed production IoT Hub V2 SLS logs with an optional 32-character hexadecimal identifier and return compact grouped JSON.
---

# LogIotHubV2

Run a read-only SLS query against this fixed target:

- Project: `k8s-log-ce84d6fe743984a3e9070b7579a100963`
- Logstore: `iot-prod`

## Language

Use Chinese for every user-visible plan, progress update, tool-action explanation, warning, and error. Keep JSON keys and all log values in their original language and spelling; add no translated labels or explanatory aliases.

## Parse the request

- Treat the first standalone value matching `^[0-9a-fA-F]{32}$` as the optional identifier and normalize it to lowercase. Proceed without an identifier predicate when no identifier is supplied. If the user explicitly supplies an identifier that is not exactly 32 hexadecimal characters, ask for a valid value; never pad, truncate, or invent one.
- Search the `traceId` field by default when an identifier is present. Use another field only when the user explicitly names it and `get-index` confirms that field is indexed.
- Use `ERROR` as the default `level`. Replace it with the requested level. Omit the level clause when the user explicitly requests all levels.
- Query the most recent 3 days by default. Resolve natural-language overrides such as “最近一周” and “最近7天” relative to the current time. Convert the resolved endpoints to Unix seconds before invoking the CLI; `--from` is inclusive and `--to` is exclusive.
- Return 10 rows by default. Use a positive row count explicitly requested by the user as the total result limit.

## Execute

Apply the installed `alibabacloud-sls-query` skill's credential, index, and observability requirements. In particular:

1. Confirm credentials only with `aliyun configure list`. Never read or display access keys.
2. Generate one fresh 32-character lowercase hexadecimal session ID for this invocation. It is independent of the user's query identifier.
3. Call `get-index` before querying and include this User-Agent on every SLS API command:

   ```text
   AlibabaCloud-Agent-Skills/alibabacloud-sls-query/{session-id}
   ```

4. Build the indexed filter from the optional identifier and level:

   - Identifier and level: `traceId: "{identifier}" and level: "ERROR"`
   - Identifier only: `traceId: "{identifier}"`
   - Level only: `level: "ERROR"`
   - Neither: `*`

   Substitute the validated field and requested level. Omit the identifier predicate when no identifier is supplied, and omit the level predicate for an explicit all-level request.

5. Use the indexed filter from step 4 as the complete `--query` value so SLS returns raw log rows. Reading raw rows preserves fields such as `message` even when their statistical index was disabled when older logs were written.

6. Execute `aliyun sls get-logs-v2` with the fixed project and Logstore, resolved timestamps, index-search pagination, chronological ordering, and exactly this client-side projection:

   ```text
   --line {page-size} --offset {offset} --reverse false
   --cli-query 'data[].{time: time, level: level, traceId: traceId, _container_name_: _container_name_, class: class, message: message}'
   ```

   For up to 100 requested rows, set `{page-size}` to the total result limit and `{offset}` to `0`. For a larger limit, fetch pages of at most 100 rows with successive offsets until the requested total is collected or a page returns no rows.

Use ordinary `--option` syntax; a leading backslash shown in prose is Markdown escaping, not part of the command.

## Return

Return exactly one fenced `json` code block with no headings, query conditions, tables, or prose before or after it. Preserve chronological row order and use this exact structure and key order:

```json
{
  "_container_name_": "biz-openapi",
  "traceId": "471f208b23844305b8aede7f97a3806b",
  "logs": [
    {
      "level": "INFO",
      "time": "2026-08-26 15:47:49.391",
      "class": "http-nio-0.0.0.0-80-exec-1.com.scin.log.track.LogFilter ",
      "message": "\n请求路径=>/biz/battery/latest/info ..."
    }
  ]
}
```

- Move the common `_container_name_` and `traceId` values to the top level and omit them from individual `logs` entries.
- Keep each log entry's keys in exactly this order: `level`, `time`, `class`, `message`.
- Preserve every returned value exactly, including surrounding whitespace and line breaks. Apply only the escaping required to produce valid JSON. Do not trim, translate, summarize, parse, or rewrite embedded JSON, SQL, or other message content.
- If rows contain multiple `_container_name_` or `traceId` pairs, group by that pair and return a JSON array of objects using the same schema.
- For no matches, return a valid object with `_container_name_` set to `null`, `traceId` set to the requested identifier or `null` when omitted, and an empty `logs` array.
- If the CLI fails, return `{"error":"中文错误信息"}` in the same single fenced `json` code block with a concise Chinese error message instead of fabricating log data.

Add no diagnosis, conclusions, annotations, numbering, Markdown lists, or post-result summary.
