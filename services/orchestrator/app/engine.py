import os
from .models import Workflow, Task, AuditEvent
from .llm import LLMClient
from .store import PostgresWorkflowStore

GRAPH = {
    "requirements": ("Normalize requirements", []),
    "design": ("Architecture and API design", ["requirements"]),
    "implementation": ("Implementation proposal", ["design"]),
    "test_plan": ("Test strategy", ["design"]),
    "validation": ("Artifact and policy validation", ["implementation", "test_plan"]),
    "documentation": ("Documentation draft", ["validation"]),
    "release_readiness": ("Release readiness review", ["documentation"]),
}
PROMPTS = {
    "requirements": "Normalize intent, acceptance criteria, assumptions, NFRs, and open questions.",
    "design": "Describe components, API contracts, data model, failures, security, scalability, and trade-offs.",
    "implementation": "Propose file-level implementation and pseudocode. Do not claim files were changed.",
    "test_plan": "List unit, integration, negative, reliability, and security tests with expected outcomes.",
    "validation": "Review prior artifacts for consistency, missing tests, policy violations, and unresolved risks.",
    "documentation": "Draft setup, API usage, operations, limitations, and rollout/rollback guidance.",
}
QUESTIONS = [
    "Which URL schemes are allowed and should private-network destinations be blocked?",
    "What is the default expiry period, if any?",
    "Should analytics be aggregate-only, and what is the retention period?",
    "What are custom alias length, allowed characters, and collision rules?",
]


def make_tasks():
    return {
        k: Task(
            id=k,
            name=n,
            dependencies=list(d),
            max_attempts=int(os.getenv("LLM_MAX_RETRIES", "2")),
        )
        for k, (n, d) in GRAPH.items()
    }


class WorkflowEngine:
    def __init__(self, llm=None, store=None):
        self.llm = llm or LLMClient()
        self.workflows = {}
        self.store = store
        if self.store is None and os.getenv("DATABASE_URL"):
            self.store = PostgresWorkflowStore(os.environ["DATABASE_URL"])
        if self.store is not None:
            for workflow in self.store.load_all():
                self.workflows[workflow.id] = workflow

    def _persist(self, wf):
        if self.store is not None:
            self.store.save(wf)

    def event(self, wf, event, task_id=None, details=None):
        wf.audit.append(AuditEvent(event=event, task_id=task_id, details=details or {}))
        self._persist(wf)

    def start(self, scenario, requirement):
        wf = Workflow(scenario=scenario, requirement=requirement, tasks=make_tasks())
        self.workflows[wf.id] = wf
        self.event(wf, "workflow_created", details={"scenario": scenario})
        if scenario == "ambiguous" and len(requirement.split()) < 12:
            wf.clarification_questions = QUESTIONS
            wf.status = "needs_clarification"
            self.event(wf, "clarification_required", details={"questions": QUESTIONS})
            return wf
        return self.run(wf.id)

    def run(self, workflow_id):
        wf = self.get(workflow_id)
        if wf.status == "needs_clarification":
            return wf
        wf.status = "running"
        for task_id in GRAPH:
            task = wf.tasks[task_id]
            if task.status == "completed" and task.artifact is not None:
                continue
            if any(wf.tasks[d].status != "completed" for d in task.dependencies):
                task.status = "blocked"
                self.event(
                    wf, "task_blocked", task_id, {"reason": "dependency_not_completed"}
                )
                continue
            if task_id == "release_readiness":
                task.status = "blocked"
                task.artifact = "Release is gated pending explicit human review."
                self.event(
                    wf, "human_approval_required", task_id, {"release_approved": False}
                )
                continue
            task.status = "running"
            while task.attempts < task.max_attempts:
                task.attempts += 1
                self.event(
                    wf, "task_attempt_started", task_id, {"attempt": task.attempts}
                )
                try:
                    context = {d: wf.tasks[d].artifact for d in task.dependencies}
                    artifact = self.llm.generate(
                        f"{task_id}: {PROMPTS[task_id]}",
                        wf.scenario,
                        wf.requirement,
                        context,
                    )
                    if not artifact or len(artifact.strip()) < 20:
                        raise RuntimeError("LLM artifact empty or too short")
                    task.artifact = artifact
                    task.status = "completed"
                    wf.artifacts[task_id] = artifact
                    self.event(
                        wf,
                        "task_completed",
                        task_id,
                        {"attempt": task.attempts, "characters": len(artifact)},
                    )
                    break
                except Exception as exc:
                    task.error = str(exc)[:1000]
                    self.event(
                        wf,
                        "task_attempt_failed",
                        task_id,
                        {"attempt": task.attempts, "error": task.error},
                    )
            if task.status != "completed":
                task.status = "failed"
                self.event(wf, "retry_exhausted", task_id, {"attempts": task.attempts})
                wf.status = "safe_stop"
                self.event(wf, "workflow_safe_stop", task_id, {"reason": task.error})
                return wf
        wf.status = "awaiting_approval"
        self.event(wf, "workflow_awaiting_approval")
        self._persist(wf)
        return wf

    def get(self, workflow_id):
        if workflow_id not in self.workflows:
            raise KeyError("Workflow not found")
        return self.workflows[workflow_id]

    def replan(self, workflow_id, new_requirement):
        wf = self.get(workflow_id)
        wf.requirement = new_requirement
        for task in wf.tasks.values():
            task.status = "stale"
            task.artifact = None
            task.error = None
            task.attempts = 0
        wf.artifacts.clear()
        wf.release_approved = False
        wf.approved_by = None
        wf.approval_comment = None
        wf.status = "running"
        self.event(
            wf, "replan_requested", details={"requirement_length": len(new_requirement)}
        )
        self._persist(wf)
        return wf

    def approve(self, workflow_id, approved_by, comment):
        wf = self.get(workflow_id)
        if wf.status != "awaiting_approval":
            raise ValueError(f"Cannot approve status {wf.status}")
        if not wf.artifacts.get("validation") or not wf.artifacts.get("test_plan"):
            raise ValueError("Validation and test plan are required")
        wf.release_approved = True
        wf.approved_by = approved_by
        wf.approval_comment = comment
        wf.status = "approved"
        task = wf.tasks["release_readiness"]
        task.status = "completed"
        task.artifact = f"Human approval by {approved_by}: {comment}"
        wf.artifacts["release_readiness"] = task.artifact
        self.event(
            wf,
            "release_approved",
            "release_readiness",
            {"approved_by": approved_by, "comment": comment},
        )
        self._persist(wf)
        return wf
