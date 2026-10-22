"""Optional PostgreSQL persistence for orchestrator workflows and append-only audit events."""
from __future__ import annotations

import json
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from .models import Workflow


class PostgresWorkflowStore:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self._initialize_schema()

    def _connect(self):
        return psycopg.connect(self.database_url, connect_timeout=5)

    def _initialize_schema(self) -> None:
        # Dedicated prefixed tables avoid touching the Spring Boot URL-shortener tables.
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS orchestrator_workflows (
                    workflow_id TEXT PRIMARY KEY,
                    scenario TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    payload JSONB NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS orchestrator_audit_events (
                    workflow_id TEXT NOT NULL REFERENCES orchestrator_workflows(workflow_id) ON DELETE CASCADE,
                    sequence_no BIGINT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    task_id TEXT,
                    details JSONB NOT NULL DEFAULT '{}'::jsonb,
                    PRIMARY KEY (workflow_id, sequence_no)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_orchestrator_workflows_status ON orchestrator_workflows(status)")

    def load_all(self) -> list[Workflow]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT payload FROM orchestrator_workflows ORDER BY created_at")
            rows = cur.fetchall()
        workflows = []
        for (payload,) in rows:
            if isinstance(payload, str):
                payload = json.loads(payload)
            workflows.append(Workflow.model_validate(payload))
        return workflows

    def save(self, workflow: Workflow) -> None:
        payload: dict[str, Any] = workflow.model_dump(mode="json")
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO orchestrator_workflows (workflow_id, scenario, status, created_at, updated_at, payload)
                VALUES (%s, %s, %s, %s::timestamptz, NOW(), %s)
                ON CONFLICT (workflow_id) DO UPDATE SET
                    scenario = EXCLUDED.scenario,
                    status = EXCLUDED.status,
                    updated_at = NOW(),
                    payload = EXCLUDED.payload
            """, (workflow.id, workflow.scenario, workflow.status, workflow.created_at, Jsonb(payload)))
            # Sequence numbers are stable within the workflow. ON CONFLICT keeps the audit table append-only.
            for sequence_no, event in enumerate(workflow.audit, start=1):
                cur.execute("""
                    INSERT INTO orchestrator_audit_events
                        (workflow_id, sequence_no, occurred_at, event_type, task_id, details)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (workflow_id, sequence_no) DO NOTHING
                """, (workflow.id, sequence_no, event.at, event.event, event.task_id, Jsonb(event.details)))
