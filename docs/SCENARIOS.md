## 1. Greenfield — Build from Scratch

**Requirement:** Build a URL shortener with custom aliases, expiry, click analytics, and safe redirects.

**Check:** Requirement analysis, design, implementation plan, tests, documentation, validation, and approval.

## 2. Brownfield — Fix Existing Code

**Requirement:** Expired links sometimes return 500. Return `410 Gone` and add regression tests without affecting valid redirects.

**Check:** Impacted code, compatibility risks, regression tests, and rollout plan.

## 3. Failure Recovery

Use an invalid API key to test retry limits and `safe_stop`.

Then replan the workflow, rerun it, review the audit history, and require human approval before release.