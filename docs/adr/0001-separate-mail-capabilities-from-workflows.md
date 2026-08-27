---
status: accepted
---

# Separate mail capabilities from workflows

The email skill exposes reusable Mail Capabilities and does not own scheduling, weekly-report recognition or comparison, Bear journal aggregation, or durable Markdown storage. Those workflows belong to the calling project because combining them with mailbox access would couple credentials and irreversible send operations to one reporting use case.
