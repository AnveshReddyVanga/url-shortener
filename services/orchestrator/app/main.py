from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from .models import WorkflowRequest, ApprovalRequest
from .engine import WorkflowEngine
from .models import CodeChangeProposalRequest, ApplyCodeChangesRequest
from .implementation import propose, apply_and_test, ImplementationError

load_dotenv()

app = FastAPI(title="Agentic Software Engineering Orchestrator", version="1.1.0")
engine = WorkflowEngine()


@app.get("/health")
def health():
    return {"status": "ok", "service": "agentic-orchestrator"}


@app.post("/workflows", status_code=201)
def create_workflow(req: WorkflowRequest):
    try:
        return engine.start(req.scenario, req.requirement)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: str):
    try:
        return engine.get(workflow_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/workflows/{workflow_id}/audit")
def get_audit(workflow_id: str):
    try:
        return engine.get(workflow_id).audit
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/workflows/{workflow_id}/replan")
def replan(workflow_id: str, req: WorkflowRequest):
    try:
        return engine.replan(workflow_id, req.requirement)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/workflows/{workflow_id}/run")
def run_workflow(workflow_id: str):
    try:
        return engine.run(workflow_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/workflows/{workflow_id}/approve-release")
def approve_release(workflow_id: str, req: ApprovalRequest):
    try:
        return engine.approve(workflow_id, req.approved_by, req.comment)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.post("/workflows/{workflow_id}/implementation/propose")
def propose_implementation(workflow_id: str, req: CodeChangeProposalRequest):
    try:
        wf = engine.get(workflow_id)
        if wf.status not in {"awaiting_approval", "approved"}:
            raise HTTPException(
                status_code=409,
                detail=f"Workflow must be awaiting_approval or approved; current status is {wf.status}",
            )
        proposal = propose(engine.llm, wf.requirement, req.instructions)
        wf.code_change_proposal = proposal
        engine.event(
            wf, "code_change_proposed", details={
                "file_count": proposal["file_count"],
                "test_files": proposal.get("test_files", []),
                "test_cases_added": proposal.get("test_cases_added", 0),
            }
        )
        return {"workflow_id": wf.id, **proposal}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ImplementationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Code proposal failed: {type(exc).__name__}: {exc}"
        )


@app.post("/workflows/{workflow_id}/implementation/apply-and-test")
def apply_implementation(workflow_id: str, req: ApplyCodeChangesRequest):
    try:
        wf = engine.get(workflow_id)
        if wf.status not in {"awaiting_approval", "approved"}:
            raise HTTPException(
                status_code=409,
                detail=f"Workflow must be awaiting_approval or approved; current status is {wf.status}",
            )
        if not wf.code_change_proposal:
            raise HTTPException(
                status_code=409,
                detail="Generate and review an implementation proposal first",
            )
        # This explicit request is the human authorization to apply the reviewed proposal.
        result = apply_and_test(wf.code_change_proposal)
        wf.implementation_execution = {
            **result,
            "approved_by": req.approved_by,
            "approval_comment": req.comment,
        }
        engine.event(
            wf,
            "implementation_applied_and_tested",
            details={
                "status": result["status"],
                "approved_by": req.approved_by,
                "rollback_performed": result.get("rollback_performed", False),
                "test_files": result.get("test_files", []),
                "test_cases_added": result.get("test_cases_added", 0),
            },
        )
        return {"workflow_id": wf.id, **wf.implementation_execution}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ImplementationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Implementation execution failed: {type(exc).__name__}: {exc}",
        )
