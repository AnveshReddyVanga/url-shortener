# Architecture

## 1. Workflow

The orchestrator follows these steps:

`Requirements → Design → Implementation → Validation → Documentation → Release Readiness`

Test planning is a separate step that connects to validation:

`Design → Test Plan → Validation`

## 2. Safety and Security

* LLM-generated output is treated as untrusted.
* The orchestrator does not execute AI-generated commands, directly modify source code, or deploy applications.
* Only a human can approve a release.
* Production requires role-based access control, signed approvals, secure audit logs, and persistent workflow storage.
* The URL service validates URLs, aliases, and expiry dates.

## 3. Controlled Implementation Pipeline

1. The LLM proposes file changes in JSON format.
2. A human reviews the proposal.
3. Changes are applied only after explicit approval.
4. File changes are restricted to approved Java source, test, and resource directories.
5. Maven tests run with `shell=False` and a timeout.
6. If testing fails or an execution error occurs, the changes are rolled back.