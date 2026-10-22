                 YOU / DEVELOPER
                        |
             +----------+----------+
             |                     |
             v                     v
    PYTHON ORCHESTRATOR       JAVA APPLICATION
    localhost:8000            localhost:8080
             |                     |
             |                     |
    /workflows                 /api/urls
             |                     |
             v                     v
    Manage development        Create short URLs
    tasks and plans           Redirect requests
    Generate code             Track analytics
    Run tests                 Validate requests
             |
             v
    Propose changes to
    Java application
             |
             v
    Apply approved changes
    and run Maven tests


======> Test the end-to-end agentic workflow

Create a workflow.
Inspect its task plan.
Inspect the audit history.
Generate an implementation proposal.
Review the proposed Java files.
Apply the changes only after the required approval.
Run Maven tests.
Verify rollback behavior if validation fails.
Inspect the final workflow state and audit history.