'use client';

import Link from 'next/link';
import React, { useEffect, useMemo, useState } from 'react';
import { Project, ProjectDomain, projectsApi, providersApi, RegistryStatus } from '@/lib/api';

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [registryStatus, setRegistryStatus] = useState<RegistryStatus | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Search & Filter State
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDomain, setSelectedDomain] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');

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
        name: name.trim(),
        description: description.trim() || undefined,
        domain,
      });
      setName('');
      setDescription('');
      setShowCreateModal(false);
      await loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to create workspace');
    } finally {
      setSubmitting(false);
    }
  };

  // Filtered projects
  const filteredProjects = useMemo(() => {
    return projects.filter((p) => {
      const matchesSearch =
        searchQuery === '' ||
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (p.description && p.description.toLowerCase().includes(searchQuery.toLowerCase()));

      const matchesDomain =
        selectedDomain === 'all' || p.domain.toLowerCase() === selectedDomain.toLowerCase();

      const matchesStatus =
        selectedStatus === 'all' || p.status.toLowerCase() === selectedStatus.toLowerCase();

      return matchesSearch && matchesDomain && matchesStatus;
    });
  }, [projects, searchQuery, selectedDomain, selectedStatus]);

  const totalTasks = useMemo(() => {
    return projects.reduce((sum, p) => sum + (p.task_count || 0), 0);
  }, [projects]);

  return (
    <div>
      {/* ── Top Header Toolbar ─────────────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: '24px',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div>
          <h1
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: '1.75rem',
              fontWeight: 600,
              color: '#F0F3F6',
              letterSpacing: '-0.02em',
              marginBottom: '4px',
            }}
          >
            Workspaces &amp; projects
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Multi-model coordination workspaces with shared FalkorDB memory graphs and deterministic DAG execution.
          </p>
        </div>

        <button
          onClick={() => setShowCreateModal(true)}
          className="btn-primary"
        >
          + New workspace
        </button>
      </div>

      {/* ── Telemetry & System Specs Bar ───────────────────────────────── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '12px',
          marginBottom: '24px',
        }}
      >
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-sm)',
            padding: '16px 20px',
          }}
        >
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 500, fontFamily: 'var(--font-mono)' }}>
            Active workspaces
          </div>
          <div style={{ fontSize: '1.5rem', fontWeight: 600, color: '#F0F3F6', marginTop: '4px', fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums' }}>
            {projects.length}
          </div>
        </div>

        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-sm)',
            padding: '16px 20px',
          }}
        >
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 500, fontFamily: 'var(--font-mono)' }}>
            Orchestrated tasks
          </div>
          <div style={{ fontSize: '1.5rem', fontWeight: 600, color: '#F0F3F6', marginTop: '4px', fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums' }}>
            {totalTasks}
          </div>
        </div>

        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-sm)',
            padding: '16px 20px',
          }}
        >
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 500, fontFamily: 'var(--font-mono)' }}>
            Registered models
          </div>
          <div style={{ fontSize: '1.5rem', fontWeight: 600, color: '#F0F3F6', marginTop: '4px', fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums' }}>
            {registryStatus?.total_registered ?? 14}{' '}
            <span style={{ fontSize: '0.85rem', fontWeight: 400, color: 'var(--text-muted)' }}>
              ({registryStatus?.configured ?? 11} configured)
            </span>
          </div>
        </div>

        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-sm)',
            padding: '16px 20px',
          }}
        >
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 500, fontFamily: 'var(--font-mono)' }}>
            Memory store
          </div>
          <div style={{ fontSize: '0.95rem', fontWeight: 500, color: '#F0F3F6', marginTop: '8px', display: 'flex', alignItems: 'center', gap: '8px', fontFamily: 'var(--font-mono)' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#40C057' }} />
            FalkorDB graph (active)
          </div>
        </div>
      </div>

      {/* ── Search & Filter Controls ───────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
          background: 'var(--bg-card)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-sm)',
          padding: '12px 16px',
          marginBottom: '20px',
        }}
      >
        {/* Search Input */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: '1', minWidth: '240px' }}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search workspaces..."
            style={{
              background: 'transparent',
              border: 'none',
              color: '#F0F3F6',
              fontSize: '0.875rem',
              width: '100%',
            }}
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '2px 6px' }}
            >
              Clear
            </button>
          )}
        </div>

        {/* Domain Filters */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
          {[
            { id: 'all', label: 'All domains' },
            { id: 'software', label: 'Software' },
            { id: 'research', label: 'Research' },
            { id: 'writing', label: 'Writing' },
            { id: 'analytics', label: 'Analytics' },
          ].map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setSelectedDomain(id)}
              style={{
                fontSize: '0.8rem',
                fontWeight: 500,
                fontFamily: 'var(--font-mono)',
                padding: '4px 10px',
                borderRadius: 'var(--radius-xs)',
                background: selectedDomain === id ? 'rgba(245, 184, 65, 0.1)' : 'transparent',
                color: selectedDomain === id ? '#F5B841' : 'var(--text-muted)',
                border: selectedDomain === id ? '1px solid rgba(245, 184, 65, 0.28)' : '1px solid transparent',
                transition: 'background-color 0.15s ease, color 0.15s ease',
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Result Count Indicator */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', fontSize: '0.8rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
        <span>
          Showing {filteredProjects.length} of {projects.length} workspaces
        </span>
      </div>

      {/* ── Project Cards Grid ─────────────────────────────────────────── */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
          Loading workspaces...
        </div>
      ) : filteredProjects.length === 0 ? (
        <div
          style={{
            padding: '50px 24px',
            textAlign: 'center',
            background: 'var(--bg-card)',
            border: '1px dashed var(--border-subtle)',
            borderRadius: '8px',
          }}
        >
          <h3 style={{ fontSize: '1.1rem', color: '#F0F3F6', marginBottom: '6px' }}>
            No matching workspaces found
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', maxWidth: '420px', margin: '0 auto 20px' }}>
            {searchQuery || selectedDomain !== 'all'
              ? 'Try adjusting your search query or domain filter.'
              : 'Create your first workspace to start orchestrating specialized AI models with shared persistent memory.'}
          </p>
          <button onClick={() => setShowCreateModal(true)} className="btn-primary">
            + Create Workspace
          </button>
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
            gap: '16px',
          }}
        >
          {filteredProjects.map((proj) => (
            <Link
              key={proj.id}
              href={`/app/projects/${proj.id}`}
              style={{
                background: 'var(--bg-card)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '8px',
                padding: '20px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                transition: 'all 0.15s ease',
                textDecoration: 'none',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.2)';
                e.currentTarget.style.transform = 'translateY(-1px)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--border-subtle)';
                e.currentTarget.style.transform = 'none';
              }}
            >
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <span
                    style={{
                      fontSize: '0.72rem',
                      fontWeight: 600,
                      fontFamily: 'var(--font-mono)',
                      textTransform: 'uppercase',
                      padding: '2px 7px',
                      borderRadius: '4px',
                      background: 'rgba(255, 255, 255, 0.05)',
                      color: 'var(--text-secondary)',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                    }}
                  >
                    {proj.domain}
                  </span>
                  <span className={`badge badge-${proj.status}`}>
                    {proj.status}
                  </span>
                </div>

                <h3 style={{ fontSize: '1.15rem', fontWeight: 600, color: '#F0F3F6', marginBottom: '8px', letterSpacing: '-0.01em' }}>
                  {proj.name}
                </h3>

                <p
                  style={{
                    fontSize: '0.85rem',
                    color: 'var(--text-secondary)',
                    lineHeight: 1.5,
                    marginBottom: '18px',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden',
                  }}
                >
                  {proj.description || 'No description provided.'}
                </p>
              </div>

              <div
                style={{
                  borderTop: '1px solid rgba(255, 255, 255, 0.06)',
                  paddingTop: '12px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontSize: '0.8rem',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-muted)',
                }}
              >
                <span>{proj.task_count || 0} tasks tracked</span>
                <span style={{ color: '#F5B841', fontWeight: 500 }}>Open workspace</span>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* ── Create Project Modal ────────────────────────────────────────── */}
      {showCreateModal && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.72)',
            backdropFilter: 'blur(6px)',
            zIndex: 100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '24px',
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowCreateModal(false);
          }}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '480px',
              padding: '24px',
              background: '#161B22',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '8px',
              boxShadow: '0 16px 36px rgba(0, 0, 0, 0.5)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2 id="modal-title" style={{ fontSize: '1.15rem', fontWeight: 600, color: '#F0F3F6', margin: 0, letterSpacing: '-0.01em' }}>
                Create workspace
              </h2>
              <button
                onClick={() => setShowCreateModal(false)}
                style={{ color: 'var(--text-muted)', fontSize: '1.1rem', padding: '4px' }}
                aria-label="Close modal"
              >
                ✕
              </button>
            </div>

            {error && (
              <div
                style={{
                  padding: '8px 12px',
                  background: 'rgba(250, 82, 82, 0.1)',
                  border: '1px solid rgba(250, 82, 82, 0.24)',
                  borderRadius: '4px',
                  color: 'var(--status-failed)',
                  fontSize: '0.85rem',
                  marginBottom: '16px',
                }}
              >
                {error}
              </div>
            )}

            <form onSubmit={handleCreate}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Workspace name *
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Distributed Telemetry Pipeline"
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    background: '#0E1116',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: '4px',
                    color: '#F0F3F6',
                    fontSize: '0.875rem',
                  }}
                />
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Domain
                </label>
                <select
                  value={domain}
                  onChange={(e) => setDomain(e.target.value as ProjectDomain)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    background: '#0E1116',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: '4px',
                    color: '#F0F3F6',
                    fontSize: '0.875rem',
                  }}
                >
                  <option value="software">Software engineering</option>
                  <option value="research">Research &amp; analysis</option>
                  <option value="writing">Documentation &amp; writing</option>
                  <option value="analytics">Data analytics &amp; metrics</option>
                  <option value="architecture">System architecture</option>
                </select>
              </div>

              <div style={{ marginBottom: '24px' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Description (optional)
                </label>
                <textarea
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="High-level objectives, architectural constraints, and deliverables..."
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    background: '#0E1116',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: '4px',
                    color: '#F0F3F6',
                    fontSize: '0.875rem',
                    resize: 'vertical',
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="btn-secondary"
                  disabled={submitting}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={submitting}
                >
                  {submitting ? 'Creating...' : 'Create workspace'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
