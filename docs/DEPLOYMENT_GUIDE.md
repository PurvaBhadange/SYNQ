# SYNQ Production Deployment Guide: Render & Vercel (Zero Cost)

This guide walks you through deploying **SYNQ** into production completely within the **₹0 free tier**:
- **Backend (FastAPI + WebSocket)**: Deployed on **Render** (Free Web Service)
- **Frontend (Next.js 16)**: Deployed on **Vercel** (Free Tier)

---

## Architecture Overview

```
┌─────────────────────────────────┐           ┌─────────────────────────────────┐
│         Vercel (Free)           │           │          Render (Free)          │
│                                 │           │                                 │
│  Next.js 16 Frontend Web App    │   HTTPS   │  FastAPI Python Backend         │
│  - Task Board & Inspector       ├──────────►│  - Deterministic Router         │
│  - Interactive Visual DAG       │    REST   │  - Multi-Agent Coordinator      │
│  - FalkorDB Memory Visualizer   │           │  - Collaborative Reviewer       │
│  - Deliverables Exporter        │    WSS    │  - SQLite Operational DB        │
│                                 │◄─────────►│  - WebSocket Real-Time Stream   │
└─────────────────────────────────┘           └─────────────────────────────────┘
```

---

## Step 1: Deploy Backend to Render (Free Web Service)

Render provides a generous free tier for Python web services with HTTPS and WebSocket support.

### Option A: Automatic Blueprint Deployment (Recommended)
1. Go to [Render Dashboard](https://dashboard.render.com/) and click **New +** -> **Blueprint**.
2. Select your GitHub repository: `PurvaBhadange/SYNQ`.
3. Render will automatically detect the [render.yaml](file:///c:/Users/purva/OneDrive/Desktop/PROJECTS/SYNQ/render.yaml) file in the root.
4. Click **Apply**.
5. Once created, open your new Web Service settings and add your free AI API keys under **Environment Variables**:
   * `GEMINI_API_KEY`: Your Google AI Studio key (free tier)
   * `GROQ_API_KEY`: Your Groq Cloud key (free tier)
   * `TAVILY_API_KEY`: Your Tavily search key (free tier)
   * `MISTRAL_API_KEY`: (Optional) Mistral AI key
   * `HF_TOKEN`: (Optional) Hugging Face token

### Option B: Manual Web Service Setup
If not using Blueprints:
1. Go to [dashboard.render.com](https://dashboard.render.com/) -> **New +** -> **Web Service**.
2. Connect your GitHub repository `PurvaBhadange/SYNQ`.
3. Configure the settings:
   * **Name**: `synq-backend`
   * **Region**: Choose closest to you (e.g. `Oregon` or `Frankfurt`)
   * **Branch**: `main`
   * **Root Directory**: `backend`
   * **Runtime**: `Python`
   * **Build Command**: `pip install -r requirements.txt`
   * **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   * **Instance Type**: `Free`
4. Under **Environment Variables**, add:
   * `PYTHON_VERSION`: `3.11.9`
   * `APP_ENV`: `production`
   * `DEBUG`: `false`
   * `SECRET_KEY`: (Click "Generate" or type a secure random string)
   * `DATABASE_URL`: `sqlite+aiosqlite:///./synq.db`
   * `FALKORDB_ENABLED`: `false`
   * `FALKORDB_ALLOW_IN_MEMORY_FALLBACK`: `false`
   * `CORS_ORIGINS`: `http://localhost:3000,http://127.0.0.1:3000`
   * Plus your AI API keys (`GEMINI_API_KEY`, `GROQ_API_KEY`, `TAVILY_API_KEY`).
5. Click **Create Web Service**.
6. When deployment finishes, copy your Render URL (e.g., `https://synq-backend.onrender.com`).
   * Test it by visiting `https://synq-backend.onrender.com/health` in your browser. It should return `{"status": "ok", "app": "SYNQ", ...}`.

---

## Step 2: Deploy Frontend to Vercel (Free Next.js Hosting)

Vercel is the creator of Next.js and provides zero-configuration hosting with global CDN.

1. Go to [Vercel Dashboard](https://vercel.com/dashboard) and click **Add New...** -> **Project**.
2. Select your GitHub repository: `PurvaBhadange/SYNQ` and click **Import**.
3. In the **Configure Project** screen:
   * **Project Name**: `synq` (or any custom name)
   * **Framework Preset**: `Next.js`
   * **Root Directory**: Click **Edit** and select `frontend` (⚠️ **CRITICAL STEP**)
4. Expand **Environment Variables** and add:
   * `NEXT_PUBLIC_API_URL`: `https://synq-backend.onrender.com/api/v1` (replace with your real Render URL)
   * `NEXT_PUBLIC_WS_URL`: `wss://synq-backend.onrender.com/api/v1/ws` (use `wss://` instead of `https://`)
5. Click **Deploy**.
6. Vercel will install dependencies, run Turbopack TypeScript checks, and deploy in ~45 seconds.
7. Copy your live Vercel production URL (e.g., `https://synq.vercel.app`).

---

## Step 3: Link Vercel Domain in Render CORS (Final Step)

To allow the frontend to communicate with the backend securely:
1. Go back to your [Render Dashboard](https://dashboard.render.com/) -> `synq-backend` -> **Environment**.
2. Update or add:
   * `FRONTEND_URL`: `https://synq.vercel.app` (your actual Vercel domain)
   * `CORS_ORIGINS`: `http://localhost:3000,https://synq.vercel.app`
3. Click **Save Changes**. Render will automatically redeploy the backend with the updated CORS policy in under 30 seconds.

---

## Verification Checklist

- [ ] Visit `https://synq-backend.onrender.com/health` -> returns `{"status": "ok"}`
- [ ] Visit `https://synq.vercel.app` -> landing page loads with animations
- [ ] Visit `https://synq.vercel.app/app` -> project workspace loads existing projects
- [ ] Click into any project -> task board, interactive DAG canvas, and export modals load
- [ ] Real-time token streaming works over WebSocket (`wss://`)
