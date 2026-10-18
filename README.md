# SYNQ — AI Agent Orchestration Platform

> **"One workspace. Multiple AI agents. Continuous project memory."**

SYNQ is a production-grade AI agent orchestration platform that coordinates multiple specialized AI models (both local and cloud) on complex tasks while maintaining shared, persistent project memory in **FalkorDB**.

---

## 🌟 Key Capabilities

1. **Continuous Project Memory in FalkorDB**
   - Every task execution, output artifact, source citation, and architectural decision is indexed into FalkorDB.
   - Downstream tasks automatically inherit tailored context packages—preventing amnesia across multi-agent workflows.

2. **Deterministic Provider Routing**
   - Algorithmic scoring evaluates task type specificity, context length, configuration status, and health cooldowns.
   - Transparent audit trails explain why an agent was selected and why alternatives were rejected.

3. **Automatic Fallback & Self-Healing**
   - If a provider encounters a rate limit, timeout, or validation failure, SYNQ degrades that model for a cooldown period and transparently cascades to the next qualified candidate.

4. **Real-Time Streaming Execution Monitor**
   - WebSocket streaming relays token generation, agent state transitions, and DAG progress directly to the frontend.

5. **Topological DAG Goal Decomposition**
   - AI Planner automatically decomposes high-level goals into directed acyclic graphs (DAGs) of specialized subtasks with dependency management.

6. **Interactive Memory Graph Visualizer**
   - Explore Project, Task, Execution, Artifact, and Decision nodes and relationships directly within the workspace.

---

## 🏗️ Architecture Overview

```
┌────────────────────────────────────────────────────────────┐
│                  SYNQ FRONTEND (Next.js 16)                │
│  Landing Page │ Dashboard │ Workspace │ Memory │ Registry  │
└──────────────────────────┬─────────────────────────────────┘
                           │ REST + WebSocket Stream
┌──────────────────────────▼─────────────────────────────────┐
│                    SYNQ BACKEND (FastAPI)                  │
│                                                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Planner  │  │  Router  │  │ Coord.   │  │ Memory   │   │
│  │ (AI+DAG) │  │(Determ.) │  │ (Stream) │  │ Service  │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │              │              │              │         │
│  ┌────▼──────────────▼──────────────▼─────────────▼─────┐   │
│  │               Capability Registry                    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                            │
│  ┌────────────────────────────────────────────────────┐    │
│  │                  Provider Layer                    │    │
│  │   Ollama (Local) │ Gemini (Cloud) │ Bedrock        │    │
│  │   (Unified Interface: BaseProvider)                │    │
│  └────────────────────────────────────────────────────┘    │
└──────────────────────────┬───────────────────────┬─────────┘
                           │                       │
                 ┌─────────▼──────┐      ┌─────────▼───────┐
                 │    FalkorDB    │      │  SQLite 3 Async │
                 │ (Graph Memory) │      │ (State & Tasks) │
                 └────────────────┘      └─────────────────┘
```

---

## 🚀 Quickstart Guide

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker (for FalkorDB)

### 1. Start FalkorDB
```bash
docker compose up -d
```
FalkorDB starts on `localhost:6379`.

### 2. Start Backend (FastAPI)
```bash
cd backend
python -m pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
- API Base: `http://localhost:8000/api/v1`
- Swagger Docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

### 3. Start Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev
```
- Workspace UI: `http://localhost:3000`

---

## 🧪 Running Tests

The test suite includes 38 comprehensive unit and integration tests covering:
- Provider interface and mock harness
- Capability registry filtering
- Deterministic routing scoring, project allow-lists, and cooldown degradation
- Output validator (Python syntax check, research citations, word count)
- Task decomposition and topological cycle detection
- Memory service graph nodes and context packages
- End-to-end coordinator execution flow and automatic fallback

Run tests:
```bash
cd backend
python -m pytest
```

---

## 🔒 Security & Privacy

- **Zero API Keys in Frontend or Source Code**: All credentials are read from backend `.env` variables.
- **Project Isolation**: Projects can specify `allowed_providers` (e.g. restrict private projects to local Ollama only).
- **Prompt Injection Defense**: Context packages structure untrusted content under data fields rather than system instructions.
- **Human-in-the-Loop**: High-impact or destructive tasks can be flagged with `requires_approval: true`, pausing execution until explicitly approved.
