'use client';

import React, { useEffect, useState } from 'react';
import { exportApi, ExportPreview } from '@/lib/api';

interface ExportModalProps {
  projectId: string;
  projectName: string;
  isOpen: boolean;
  onClose: () => void;
}

export default function ExportModal({
  projectId,
  projectName,
  isOpen,
  onClose,
}: ExportModalProps) {
  const [preview, setPreview] = useState<ExportPreview | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [downloadingZip, setDownloadingZip] = useState<boolean>(false);
  const [downloadingMd, setDownloadingMd] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    exportApi
      .getPreview(projectId)
      .then((data) => {
        if (isMounted) {
          setPreview(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Failed to load export preview');
          setLoading(false);
        }
      });

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      isMounted = false;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, projectId, onClose]);

  if (!isOpen) return null;

  const handleDownloadZip = () => {
    setDownloadingZip(true);
    const url = exportApi.getZipUrl(projectId);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${projectName.toLowerCase().replace(/[^a-z0-9_-]/g, '_')}_deliverables.zip`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => setDownloadingZip(false), 2000);
  };

  const handleDownloadMarkdown = () => {
    setDownloadingMd(true);
    const url = exportApi.getMarkdownUrl(projectId);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${projectName.toLowerCase().replace(/[^a-z0-9_-]/g, '_')}_dossier.md`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => setDownloadingMd(false), 2000);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="export-modal-title"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        backgroundColor: 'rgba(5, 5, 10, 0.85)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="glass-panel"
        style={{
          width: '100%',
          maxWidth: '680px',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: '#0c0e14',
          border: '1px solid rgba(255, 255, 255, 0.12)',
          boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.7)',
          borderRadius: '16px',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '20px 24px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.2rem' }}>📦</span>
              <h2 id="export-modal-title" style={{ fontSize: '1.25rem', fontWeight: 700, color: '#fff', margin: 0 }}>
                Export Project Deliverables
              </h2>
            </div>
            <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Project: <strong style={{ color: '#fff' }}>{projectName}</strong>
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close export modal"
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              fontSize: '1.5rem',
              cursor: 'pointer',
              padding: '4px',
              borderRadius: '6px',
            }}
          >
            ×
          </button>
        </div>

        {/* Content Body */}
        <div style={{ padding: '24px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {error && (
            <div
              style={{
                padding: '12px 16px',
                borderRadius: '8px',
                background: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#fca5a5',
                fontSize: '0.9rem',
              }}
            >
              ⚠️ {error}
            </div>
          )}

          {/* Security & Scrubbing Notice */}
          <div
            style={{
              padding: '14px 18px',
              borderRadius: '10px',
              background: 'rgba(34, 197, 94, 0.08)',
              border: '1px solid rgba(34, 197, 94, 0.25)',
              display: 'flex',
              gap: '12px',
              alignItems: 'flex-start',
            }}
          >
            <span style={{ fontSize: '1.2rem', marginTop: '2px' }}>🛡️</span>
            <div style={{ fontSize: '0.85rem', color: '#bbf7d0', lineHeight: 1.5 }}>
              <strong>Zero-Cost & Secret Redaction Guarantee:</strong> All exports are sanitized against path traversal
              and strictly exclude sensitive files (e.g. <code>.env</code>, <code>*.key</code>, <code>synq.db</code>).
              Discovered cloud API keys are scrubbed and replaced with <code>[REDACTED_SECRET]</code> prior to compression.
            </div>
          </div>

          {/* Export Options Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            {/* ZIP Card */}
            <div
              style={{
                padding: '18px',
                borderRadius: '12px',
                background: 'rgba(255, 255, 255, 0.03)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                gap: '14px',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <span style={{ fontSize: '1.4rem' }}>🗜️</span>
                  <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#fff', margin: 0 }}>
                    ZIP Archive
                  </h3>
                </div>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.4 }}>
                  Comprehensive distribution package containing verified task outputs, <code>manifest.json</code>,
                  dependency graph, and dossier.
                </p>
              </div>

              <button
                onClick={handleDownloadZip}
                disabled={downloadingZip}
                className="btn-primary"
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  fontSize: '0.88rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                }}
              >
                {downloadingZip ? 'Preparing Archive...' : 'Download ZIP Archive'}
              </button>
            </div>

            {/* Markdown Dossier Card */}
            <div
              style={{
                padding: '18px',
                borderRadius: '12px',
                background: 'rgba(255, 255, 255, 0.03)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                gap: '14px',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <span style={{ fontSize: '1.4rem' }}>📄</span>
                  <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#fff', margin: 0 }}>
                    Markdown Dossier
                  </h3>
                </div>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.4 }}>
                  Human-readable audit report containing project overview, task outputs, validation results, peer reviews,
                  and architectural decisions.
                </p>
              </div>

              <button
                onClick={handleDownloadMarkdown}
                disabled={downloadingMd}
                className="btn-secondary"
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  fontSize: '0.88rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                }}
              >
                {downloadingMd ? 'Generating...' : 'Download Markdown (.md)'}
              </button>
            </div>
          </div>

          {/* Deliverables Preview List */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                MANIFEST PREVIEW
              </span>
              {preview && (
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  {preview.completed_task_count} of {preview.total_task_count} tasks completed
                </span>
              )}
            </div>

            <div
              style={{
                padding: '12px 16px',
                borderRadius: '8px',
                background: '#07080c',
                border: '1px solid rgba(255, 255, 255, 0.06)',
                fontFamily: 'monospace',
                fontSize: '0.8rem',
                maxHeight: '150px',
                overflowY: 'auto',
                color: 'var(--text-secondary)',
              }}
            >
              {loading ? (
                <div>Scanning eligible deliverables...</div>
              ) : preview && preview.deliverable_files.length > 0 ? (
                preview.deliverable_files.map((file, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '3px 0' }}>
                    <span style={{ color: 'var(--accent-orange)' }}>📁</span>
                    <span>{file}</span>
                  </div>
                ))
              ) : (
                <div>No deliverables generated yet. Complete tasks to export code and reports.</div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '16px 24px',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            justifyContent: 'flex-end',
          }}
        >
          <button
            onClick={onClose}
            className="btn-secondary"
            style={{ padding: '8px 20px', fontSize: '0.9rem' }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
