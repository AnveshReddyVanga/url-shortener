from app.engine import WorkflowEngine


class FakeLLM:
    def generate(self, stage, scenario, requirement, context):
        return f"Artifact for {stage}. Requirement analyzed: {requirement}. Risks and validation included."


def test_greenfield_awaits_approval():
    e = WorkflowEngine(FakeLLM())
    w = e.start(
        "greenfield", "Build a URL shortener with aliases, expiry, and analytics."
    )
    assert (
        w.status == "awaiting_approval"
        and w.tasks["implementation"].status == "completed"
        and w.tasks["release_readiness"].status == "blocked"
    )


def test_ambiguous_requires_clarification():
    e = WorkflowEngine(FakeLLM())
    w = e.start("ambiguous", "Make links safer.")
    assert w.status == "needs_clarification" and len(w.clarification_questions) >= 3


def test_approval_is_explicit():
    e = WorkflowEngine(FakeLLM())
    w = e.start("greenfield", "Build a URL shortener with expiration and analytics.")
    w = e.approve(w.id, "reviewer@example.com", "Artifacts reviewed")
    assert w.status == "approved" and w.release_approved


def test_replan_invalidates_artifacts():
    e = WorkflowEngine(FakeLLM())
    w = e.start("greenfield", "Build a URL shortener with aliases and analytics.")
    e.replan(w.id, "Change expiry behavior and retention requirements.")
    assert w.tasks["requirements"].status == "stale" and not w.artifacts


def test_retries_safe_stop():
    class Broken:
        def generate(self, *a, **kw):
            raise RuntimeError("provider unavailable")

    e = WorkflowEngine(Broken())
    w = e.start("greenfield", "Build a URL shortener with aliases and analytics.")
    assert w.status == "safe_stop" and w.tasks["requirements"].status == "failed"


def test_workflow_state_is_saved_and_restored_with_store():
    class FakeStore:
        def __init__(self):
            self.saved = {}

        def load_all(self):
            return list(self.saved.values())

        def save(self, workflow):
            # Workflow objects are mutable; retain a serialized snapshot as a real store would.
            from app.models import Workflow
            self.saved[workflow.id] = Workflow.model_validate(workflow.model_dump(mode="json"))

    store = FakeStore()
    first_engine = WorkflowEngine(FakeLLM(), store=store)
    created = first_engine.start(
        "ambiguous", "Make links safer for users and reduce malicious redirects."
    )
    assert created.id in store.saved

    restarted_engine = WorkflowEngine(FakeLLM(), store=store)
    restored = restarted_engine.get(created.id)
    assert restored.id == created.id
    assert restored.status == "needs_clarification"
    assert any(event.event == "clarification_required" for event in restored.audit)
