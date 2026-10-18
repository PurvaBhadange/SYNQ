'use client';

import Link from 'next/link';
import React, { useEffect, useState } from 'react';
import { Project, ProjectDomain, projectsApi, providersApi, RegistryStatus } from '@/lib/api';

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [registryStatus, setRegistryStatus] = useState<RegistryStatus | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Form State
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [domain, setDomain] = useState<ProjectDomain>('software');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      const [projList, regInfo] = await Promise.all([
        projectsApi.list().catch(() => []),
        providersApi.list().catch(() => null),
      ]);
      setProjects(projList);
      setRegistryStatus(regInfo);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    // Auto-retry after 6s in case backend was spinning up from cold start
    const timer = setTimeout(() => {
      loadData();
    }, 6000);
    return () => clearTimeout(timer);
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      setSubmitting(true);
      setError(null);
      await projectsApi.create({
        name,
        description: description.trim() || undefined,
        domain,
      });
      setName('');
      setDescription('');
      setShowCreateModal(false);
      await loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to create project');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      {/* ── Top Overview Banner ─────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div>
          <h1 className="font-serif" style={{ fontSize: '2rem', color: '#fff', marginBottom: '6px' }}>
            Workspaces & Projects
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
            Manage autonomous agent workspaces with shared FalkorDB memory graphs.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn-primary"
          style={{ padding: '10px 24px' }}
        >
          + Create Project
        </button>
      </div>

      {/* ── Stats Row ───────────────────────────────────────────────────── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '16px',
          marginBottom: '36px',
        }}
      >
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
            Active Projects
          </div>
          <div style={{ fontSize: '2.2rem', fontWeight: 800, color: '#fff', marginTop: '4px' }}>
            {projects.length}
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
            Total Tasks
          </div>
          <div style={{ fontSize: '2.2rem', fontWeight: 800, color: 'var(--accent-orange)', marginTop: '4px' }}>
            {projects.reduce((sum, p) => sum + (p.task_count || 0), 0)}
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
            Registered AI Models
          </div>
          <div style={{ fontSize: '2.2rem', fontWeight: 800, color: 'var(--status-running)', marginTop: '4px' }}>
            {registryStatus?.total_registered ?? 3}
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
            Memory Store
          </div>
          <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--status-completed)', marginTop: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="pulse-dot" style={{ backgroundColor: 'var(--status-completed)' }}></span>
            FalkorDB (Active)
          </div>
        </div>
      </div>

      {/* ── Project Cards Grid ─────────────────────────────────────────── */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
          Loading workspaces...
        </div>
      ) : projects.length === 0 ? (
        <div
          className="glass-panel"
          style={{
            padding: '60px 24px',
            textAlign: 'center',
            borderStyle: 'dashed',
            borderColor: 'rgba(255, 255, 255, 0.15)',
          }}
        >
          <div style={{ fontSize: '2.5rem', marginBottom: '12px' }}>🚀</div>
          <h3 style={{ fontSize: '1.3rem', color: '#fff', marginBottom: '8px' }}>
            No projects yet
          </h3>
          <p style={{ color: 'var(--text-secondary)', maxWidth: '440px', margin: '0 auto 24px' }}>
            Create your first workspace to start orchestrating specialized AI models with shared persistent memory.
          </p>
          <button onClick={() => setShowCreateModal(true)} className="btn-primary">
            + Create First Project
          </button>
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
            gap: '24px',
          }}
        >
          {projects.map((proj) => (
            <Link
              key={proj.id}
              href={`/app/projects/${proj.id}`}
              className="glass-panel"
              style={{
                padding: '24px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                transition: 'all 0.2s ease',
                position: 'relative',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--border-focus)';
                e.currentTarget.style.transform = 'translateY(-2px)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--border-subtle)';
                e.currentTarget.style.transform = 'none';
              }}
            >
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                  <span
                    style={{
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      padding: '3px 8px',
                      borderRadius: '4px',
                      background: 'rgba(255, 255, 255, 0.06)',
                      color: 'var(--accent-orange-light)',
                    }}
                  >
                    {proj.domain}
                  </span>
                  <span className={`badge badge-${proj.status}`}>
                    {proj.status}
                  </span>
                </div>

                <h3 style={{ fontSize: '1.25rem', color: '#fff', marginBottom: '8px' }}>
                  {proj.name}
                </h3>

                <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: '20px' }}>
                  {proj.description || 'No description provided.'}
                </p>
              </div>

              <div
                style={{
                  borderTop: '1px solid var(--border-subtle)',
                  paddingTop: '14px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontSize: '0.85rem',
                  color: 'var(--text-muted)',
                }}
              >
                <span>{proj.task_count || 0} tasks tracked</span>
                <span style={{ color: 'var(--accent-orange)', fontWeight: 600 }}>Open Workspace →</span>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* ── Create Project Modal ────────────────────────────────────────── */}
      {showCreateModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(8px)',
            zIndex: 100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
        >
          <div
            className="glass-panel"
            style={{
              width: '100%',
              maxWidth: '520px',
              padding: '32px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2 className="font-serif" style={{ fontSize: '1.5rem', color: '#fff' }}>
                Create New Project
              </h2>
              <button
                onClick={() => setShowCreateModal(false)}
                style={{ color: 'var(--text-muted)', fontSize: '1.4rem' }}
              >
                ✕
              </button>
            </div>

            {error && (
              <div style={{ padding: '10px 14px', background: 'rgba(255, 107, 107, 0.15)', color: '#ff6b6b', borderRadius: '8px', fontSize: '0.85rem', marginBottom: '16px' }}>
                {error}
              </div>
            )}

            <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Project Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Distributed Search Engine"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    background: 'var(--bg-primary)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    color: '#fff',
                    fontSize: '0.95rem',
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Domain
                </label>
                <select
                  value={domain}
                  onChange={(e) => setDomain(e.target.value as ProjectDomain)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    background: 'var(--bg-primary)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    color: '#fff',
                    fontSize: '0.95rem',
                  }}
                >
                  <option value="software">Software Engineering</option>
                  <option value="research">Research & Science</option>
                  <option value="content">Content & Writing</option>
                  <option value="business">Business & Product</option>
                  <option value="education">Education</option>
                  <option value="general">General Purpose</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Description
                </label>
                <textarea
                  rows={3}
                  placeholder="Goals, boundaries, and expected deliverables..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    background: 'var(--bg-primary)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    color: '#fff',
                    fontSize: '0.95rem',
                    resize: 'vertical',
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '12px' }}>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="btn-primary"
                >
                  {submitting ? 'Creating...' : 'Create Project'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
