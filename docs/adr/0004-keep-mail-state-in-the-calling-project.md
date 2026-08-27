---
status: accepted
---

# Keep mail state in the calling project

All file-based account configuration, Prepared Drafts, previews, downloaded attachments, and temporary mail state live under a Git-ignored `.mailctl/` directory in the Calling Project rather than in the skill installation, a global application directory, or the server Drafts mailbox. The Calling Project is exactly the process working directory; the CLI neither searches parent directories nor writes outside it. This keeps every generated resource inside the directory that invoked the skill without making the reusable Mail Capability own the surrounding workflow; the CLI refuses to use state files tracked by Git and does not maintain a general operation audit log. The third-party client security password remains in macOS Keychain and is never written as a project resource.
