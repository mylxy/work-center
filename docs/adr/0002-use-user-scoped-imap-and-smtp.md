---
status: accepted
---

# Use user-scoped IMAP and SMTP for Alibaba Mail

The first version connects to Alibaba Mail through IMAP and SMTP over TLS with a user-owned third-party client security password. The administrator-managed API was rejected for now because its public documentation does not establish that an application credential can be restricted to one mailbox; the API can be reconsidered if that scope is verified later.
