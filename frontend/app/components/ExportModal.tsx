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
          backgroundColor: '#161B22',
          border: '1px solid #2A313C',
          boxShadow: '0 20px 40px rgba(0, 0, 0, 0.6)',
          borderRadius: '8px',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '1rem 1.25rem',
            borderBottom: '1px solid #2A313C',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#F5B841" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              <h2 id="export-modal-title" style={{ fontSize: '1rem', fontWeight: 600, color: '#E6EDF3', margin: 0 }}>
                Export project deliverables
              </h2>
            </div>
            <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem', color: '#8B949E' }}>
              Project: <strong style={{ color: '#E6EDF3', fontWeight: 500 }}>{projectName}</strong>
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close export modal"
            style={{
              background: 'none',
              border: 'none',
              color: '#8B949E',
              fontSize: '1.25rem',
              cursor: 'pointer',
              padding: '4px',
              lineHeight: 1,
            }}
          >
            ✕
          </button>
        </div>

        {/* Content Body */}
        <div style={{ padding: '1.25rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {error && (
            <div
              style={{
                padding: '0.75rem 1rem',
                borderRadius: '6px',
                background: '#291013',
                border: '1px solid #66242B',
                color: '#FCA5A5',
                fontSize: '0.85rem',
              }}
            >
              Error: {error}
            </div>
          )}

          {/* Security & Scrubbing Notice */}
          <div
            style={{
              padding: '0.75rem 1rem',
              borderRadius: '6px',
              background: '#0E2318',
              border: '1px solid #1D5A38',
              display: 'flex',
              gap: '0.75rem',
              alignItems: 'flex-start',
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginTop: '2px' }} aria-hidden="true">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <div style={{ fontSize: '0.8rem', color: '#86EFAC', lineHeight: 1.5 }}>
              <strong style={{ color: '#E6EDF3', fontWeight: 600 }}>Secret redaction and path traversal guarantee:</strong> All exports are sanitized against directory traversal
              and strictly exclude environment files (e.g. <code>.env</code>, <code>*.key</code>, <code>synq.db</code>).
              Discovered cloud API keys are scrubbed and replaced with <code>[REDACTED_SECRET]</code> prior to compression.
            </div>
          </div>

          {/* Export Options Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            {/* ZIP Card */}
            <div
              style={{
                padding: '1rem',
                borderRadius: '6px',
                background: '#0E1116',
                border: '1px solid #2A313C',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                gap: '1rem',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#F5B841" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <polyline points="21 8 21 21 3 21 3 8" />
                    <rect x="1" y="3" width="22" height="5" />
                    <line x1="10" y1="12" x2="14" y2="12" />
                  </svg>
                  <h3 style={{ fontSize: '0.92rem', fontWeight: 600, color: '#E6EDF3', margin: 0 }}>
                    ZIP archive
                  </h3>
                </div>
                <p style={{ fontSize: '0.8rem', color: '#8B949E', margin: 0, lineHeight: 1.45 }}>
                  Distribution package containing verified task outputs, <code>manifest.json</code>,
                  dependency graph, and dossier.
                </p>
              </div>

              <button
                onClick={handleDownloadZip}
                disabled={downloadingZip}
                className="btn-primary"
                style={{
                  width: '100%',
                  padding: '0.5rem 1rem',
                  fontSize: '0.85rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem',
                }}
              >
                {downloadingZip ? 'Preparing archive...' : 'Download ZIP archive'}
              </button>
            </div>

            {/* Markdown Dossier Card */}
            <div
              style={{
                padding: '1rem',
                borderRadius: '6px',
                background: '#0E1116',
                border: '1px solid #2A313C',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                gap: '1rem',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8B949E" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="16" y1="13" x2="8" y2="13" />
                    <line x1="16" y1="17" x2="8" y2="17" />
                    <polyline points="10 9 9 9 8 9" />
                  </svg>
                  <h3 style={{ fontSize: '0.92rem', fontWeight: 600, color: '#E6EDF3', margin: 0 }}>
                    Markdown dossier
                  </h3>
                </div>
                <p style={{ fontSize: '0.8rem', color: '#8B949E', margin: 0, lineHeight: 1.45 }}>
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
                  padding: '0.5rem 1rem',
                  fontSize: '0.85rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem',
                }}
              >
                {downloadingMd ? 'Generating...' : 'Download markdown (.md)'}
              </button>
            </div>
          </div>

          {/* Deliverables Preview List */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#8B949E', letterSpacing: '0.02em' }}>
                Manifest preview
              </span>
              {preview && (
                <span style={{ fontSize: '0.75rem', color: '#8B949E', fontVariantNumeric: 'tabular-nums' }}>
                  {preview.completed_task_count} of {preview.total_task_count} tasks completed
                </span>
              )}
            </div>

            <div
              style={{
                padding: '0.75rem 1rem',
                borderRadius: '6px',
                background: '#0E1116',
                border: '1px solid #2A313C',
                fontFamily: 'monospace',
                fontSize: '0.8rem',
                maxHeight: '140px',
                overflowY: 'auto',
                color: '#8B949E',
              }}
            >
              {loading ? (
                <div>Scanning eligible deliverables...</div>
              ) : preview && preview.deliverable_files.length > 0 ? (
                preview.deliverable_files.map((file, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.2rem 0' }}>
                    <span style={{ color: '#F5B841' }}>›</span>
                    <span style={{ color: '#E6EDF3' }}>{file}</span>
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
            padding: '0.75rem 1.25rem',
            borderTop: '1px solid #2A313C',
            display: 'flex',
            justifyContent: 'flex-end',
            backgroundColor: '#0E1116',
          }}
        >
          <button
            onClick={onClose}
            className="btn-secondary"
            style={{ padding: '0.4rem 1rem', fontSize: '0.85rem' }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
