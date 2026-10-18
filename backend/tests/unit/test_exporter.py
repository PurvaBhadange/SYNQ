"""
Unit tests for Project Artifact Exporter (ZIP archive, Markdown dossier, sanitization, secret scrubbing).
"""

import io
import json
import os
from pathlib import Path
import zipfile
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from api.v1.export import (
    sanitize_filename,
    redact_secrets,
    build_markdown_dossier,
    FORBIDDEN_FILE_PATTERNS,
)
from db.models import Project, Task, TaskExecution, TaskStatus, TaskType, ExecutionStatus
from db.session import get_session_context, get_db
from main import app


@pytest_asyncio.fixture
async def sample_export_project():
    async with get_session_context() as session:
        proj = Project(
            name="Exporter Test Project",
            domain="software",
            description="Testing automated deliverables exporter",
        )
        session.add(proj)
        await session.flush()

        task1 = Task(
            project_id=proj.id,
            title="Generate API Schema",
            task_type=TaskType.CODE.value,
            status=TaskStatus.COMPLETED.value,
            priority=7,
            acceptance_criteria="FastAPI schema with tests",
            approval_reason="Verified by operator",
            approved_by="Lead Engineer",
        )
        session.add(task1)
        await session.flush()

        exec1 = TaskExecution(
            task_id=task1.id,
            provider_id="ollama",
            model_id="qwen2.5:latest",
            status=ExecutionStatus.SUCCEEDED.value,
            output_raw="def get_schema():\n    # API key: AIzaSyA1234567890123456789012345678901\n    return {'version': '1.0'}",
        )
        session.add(exec1)
        await session.commit()
        await session.refresh(proj)
        return proj


def test_sanitize_filename_path_traversal():
    """Verify that path traversal attempts are neutralized."""
    cleaned = sanitize_filename("../../etc/passwd")
    assert ".." not in cleaned
    assert not cleaned.startswith("/")

    cleaned_win = sanitize_filename("..\\..\\windows\\system32\\calc.exe")
    assert ".." not in cleaned_win
    assert "\\" not in cleaned_win

    assert sanitize_filename("") == "untitled_artifact"


def test_sanitize_filename_forbidden_secrets():
    """Verify that sensitive secret files raise ValueError."""
    forbidden_examples = [
        ".env",
        ".env.local",
        "secret.key",
        "server.pem",
        "id_rsa",
        "id_rsa.pub",
        "synq.db",
        "credentials.json",
    ]
    for filename in forbidden_examples:
        with pytest.raises(ValueError):
            sanitize_filename(filename)

    with pytest.raises(ValueError):
        sanitize_filename(f"nested/folder/{forbidden_examples[0]}")


def test_redact_secrets():
    """Verify that known cloud keys and passwords are redacted from text deliverables."""
    text_with_secrets = (
        "Here is my config:\n"
        "GEMINI_API_KEY=AIzaSyA1234567890123456789012345678901\n"
        "GROQ_KEY=gsk_1234567890abcdef1234567890abcdef1234567890\n"
        "HF_KEY=hf_1234567890abcdef1234567890abcdef\n"
        "TAVILY_KEY=tvly-1234567890abcdef1234567890abcdef\n"
        "Safe content without secrets."
    )
    scrubbed = redact_secrets(text_with_secrets)
    assert "AIzaSy" not in scrubbed
    assert "gsk_" not in scrubbed
    assert "hf_" not in scrubbed
    assert "tvly-" not in scrubbed
    assert "[REDACTED_SECRET]" in scrubbed
    assert "Safe content without secrets." in scrubbed


def test_build_markdown_dossier_content():
    """Verify Markdown dossier generation contains structured sections."""
    project = Project(
        id="test-proj-dossier",
        name="Security Audit Proj",
        domain="finance",
        description="A financial audit agent project",
    )
    task1 = Task(
        id="t-1",
        project_id="test-proj-dossier",
        title="Extract Ledger Records",
        task_type=TaskType.CODE.value,
        status=TaskStatus.COMPLETED.value,
        priority=8,
        acceptance_criteria="JSON ledger records validated.",
        approval_reason="Verified by operator",
        approved_by="Auditor1",
    )
    execution1 = TaskExecution(
        id="exec-1",
        task_id="t-1",
        status=ExecutionStatus.SUCCEEDED.value,
        output_raw="def extract_records():\n    return {'records': 100}",
    )
    task1.executions = [execution1]

    dossier = build_markdown_dossier(
        project,
        [task1],
        {"nodes": [{"label": "Decision", "description": "Used SQLite", "rationale": "Zero cost"}]},
    )

    assert "# Project Dossier: Security Audit Proj" in dossier
    assert "Extract Ledger Records" in dossier
    assert "def extract_records():" in dossier
    assert "Used SQLite" in dossier
    assert "Zero-cost" in dossier


@pytest.mark.asyncio
async def test_export_preview_endpoint(sample_export_project):
    """Test previewing exportable deliverables."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/projects/{sample_export_project.id}/export/preview")
        assert res.status_code == 200
        data = res.json()
        assert data["project_id"] == sample_export_project.id
        assert "manifest.json" in data["deliverable_files"]
        assert "dossier.md" in data["deliverable_files"]
        assert "zip" in data["formats_supported"]
        assert data["completed_task_count"] >= 1

        # Nonexistent project returns 404
        res404 = await ac.get("/api/v1/projects/nonexistent-id/export/preview")
        assert res404.status_code == 404


@pytest.mark.asyncio
async def test_export_markdown_endpoint(sample_export_project):
    """Test downloading Markdown dossier endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/projects/{sample_export_project.id}/export/markdown")
        assert res.status_code == 200
        assert "text/markdown" in res.headers["content-type"]
        assert "attachment; filename=" in res.headers["content-disposition"]
        assert len(res.text) > 0
        assert sample_export_project.name in res.text


@pytest.mark.asyncio
async def test_export_zip_archive_endpoint(sample_export_project):
    """Test generating, streaming, and inspecting a project ZIP archive."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/projects/{sample_export_project.id}/export/zip")
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/zip"
        assert "attachment; filename=" in res.headers["content-disposition"]

        # Verify ZIP contents
        zip_bytes = io.BytesIO(res.content)
        with zipfile.ZipFile(zip_bytes, "r") as zf:
            file_names = zf.namelist()
            assert "manifest.json" in file_names
            assert "docs/PROJECT_DOSSIER.md" in file_names
            assert "dependencies.json" in file_names

            # Verify manifest
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            assert manifest["project_id"] == sample_export_project.id
            assert manifest["project_name"] == sample_export_project.name

            # Verify secret redaction inside deliverable file
            deliverable_files = [fn for fn in file_names if fn.startswith("deliverables/")]
            assert len(deliverable_files) > 0
            file_content = zf.read(deliverable_files[0]).decode("utf-8")
            assert "AIzaSy" not in file_content
            assert "[REDACTED_SECRET]" in file_content
