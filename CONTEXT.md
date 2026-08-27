# Yunxiao Work Item Skill

This context defines the language used by a personal Codex skill for interacting with Yunxiao project work items.

## Language

**Work Item**:
A unit of project work managed by Yunxiao, including defects, requirements, tasks, and risks.
_Avoid_: Issue, ticket

**Defect**:
A Work Item whose Yunxiao category is `Bug`.
_Avoid_: Generic issue, generic work item

**Work Item ID**:
The opaque identifier that uniquely identifies a Work Item to Yunxiao APIs.
_Avoid_: Work Item Number, defect number

**Work Item Number**:
The human-visible, project-scoped identifier of a Work Item, such as `DSDD-123`.
_Avoid_: Work Item ID

**Status**:
A workflow state available to a Work Item; its display name is distinct from its opaque status ID.
_Avoid_: Arbitrary status label
