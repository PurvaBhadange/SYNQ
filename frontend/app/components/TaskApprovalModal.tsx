'use client';

import React, { useEffect, useState } from 'react';
import { Task, TaskApprovalContext, tasksApi } from '@/lib/api';

interface TaskApprovalModalProps {
  taskId: string;
  isOpen: boolean;
  onClose: () => void;
  onActionComplete: () => void;
}

export default function TaskApprovalModal({
  taskId,
  isOpen,
  onClose,
  onActionComplete,
}: TaskApprovalModalProps) {
  const [context, setContext] = useState<TaskApprovalContext | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Sub-views: 'overview', 'reject', 'edit'
  const [view, setView] = useState<'overview' | 'reject' | 'edit'>('overview');

  // Form states
  const [approvalReason, setApprovalReason] = useState<string>('Approved by human operator after review');
  const [approverName, setApproverName] = useState<string>('Human Operator');
  const [rejectionReason, setRejectionReason] = useState<string>('');
  const [editTitle, setEditTitle] = useState<string>('');
  const [editDescription, setEditDescription] = useState<string>('');
  const [editCriteria, setEditCriteria] = useState<string>('');

  useEffect(() => {
    if (isOpen && taskId) {
      loadContext();
    }
  }, [isOpen, taskId]);

  const loadContext = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await tasksApi.getApprovalContext(taskId);
      setContext(data);
      setEditTitle(data.title);
      setEditDescription(data.description || '');
      setEditCriteria(data.acceptance_criteria || '');
    } catch (err: any) {
      setError(err.message || 'Failed to load approval context');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const handleApprove = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await tasksApi.approve(taskId, {
        reason: approvalReason,
        approver: approverName,
      });
      onActionComplete();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Approval failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!rejectionReason.trim()) {
      setError('Please provide a reason for rejecting the task.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await tasksApi.reject(taskId, rejectionReason, approverName);
      onActionComplete();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Rejection failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEditAndResubmit = async () => {
    if (!editTitle.trim()) {
      setError('Title cannot be empty.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await tasksApi.edit(taskId, {
        title: editTitle,
        description: editDescription,
        acceptance_criteria: editCriteria,
      });
      onActionComplete();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to update task');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="approval-modal-title"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(6px)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1.5rem',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="modal-card"
        style={{
          backgroundColor: '#12141a',
          border: '1px solid rgba(245, 158, 11, 0.4)',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 30px rgba(245, 158, 11, 0.15)',
          borderRadius: '12px',
          width: '100%',
          maxWidth: '720px',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          color: '#e2e8f0',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '1.25rem 1.5rem',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'linear-gradient(90deg, rgba(245, 158, 11, 0.1) 0%, rgba(26, 29, 36, 0.6) 100%)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span
              style={{
                display: 'inline-block',
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                backgroundColor: '#f59e0b',
                boxShadow: '0 0 10px #f59e0b',
              }}
            />
            <h2
              id="approval-modal-title"
              style={{ fontSize: '1.15rem', fontWeight: 600, margin: 0, color: '#f8fafc' }}
            >
              Human-in-the-Loop Governance
            </h2>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                padding: '0.2rem 0.6rem',
                borderRadius: '9999px',
                backgroundColor: 'rgba(245, 158, 11, 0.2)',
                color: '#fbbf24',
                border: '1px solid rgba(245, 158, 11, 0.4)',
              }}
            >
              Awaiting Approval
            </span>
          </div>
          <button
            onClick={onClose}
            aria-label="Close modal"
            style={{
              background: 'transparent',
              border: 'none',
              color: '#94a3b8',
              fontSize: '1.25rem',
              cursor: 'pointer',
              padding: '0.25rem',
            }}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '1.5rem', overflowY: 'auto', flex: 1 }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '2rem', color: '#94a3b8' }}>
              Loading task approval context...
            </div>
          ) : error && !context ? (
            <div style={{ padding: '1rem', backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#fca5a5', borderRadius: '8px' }}>
              {error}
            </div>
          ) : context ? (
            <>
              {error && (
                <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#fca5a5', borderRadius: '6px', fontSize: '0.9rem' }}>
                  {error}
                </div>
              )}

              {/* View 1: Overview & Decision */}
              {view === 'overview' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                  {/* Task Objective */}
                  <div style={{ backgroundColor: 'rgba(255, 255, 255, 0.03)', padding: '1rem', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
                    <div style={{ fontSize: '0.8rem', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '0.25rem' }}>
                      Task Objective
                    </div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 600, color: '#f8fafc' }}>
                      {context.title}
                    </div>
                    {context.description && (
                      <p style={{ marginTop: '0.5rem', fontSize: '0.92rem', color: '#cbd5e1', lineHeight: 1.5 }}>
                        {context.description}
                      </p>
                    )}
                    <div style={{ display: 'flex', gap: '1rem', marginTop: '0.75rem', fontSize: '0.85rem' }}>
                      <span style={{ color: '#94a3b8' }}>
                        Type: <strong style={{ color: '#60a5fa' }}>{context.task_type}</strong>
                      </span>
                      <span style={{ color: '#94a3b8' }}>
                        Priority: <strong style={{ color: '#e2e8f0' }}>{context.priority}/10</strong>
                      </span>
                      {context.assigned_provider && (
                        <span style={{ color: '#94a3b8' }}>
                          Model: <strong style={{ color: '#34d399' }}>{context.assigned_provider} / {context.assigned_model}</strong>
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Reason approval required */}
                  <div style={{ backgroundColor: 'rgba(245, 158, 11, 0.08)', padding: '0.9rem 1rem', borderRadius: '8px', border: '1px solid rgba(245, 158, 11, 0.25)' }}>
                    <div style={{ fontSize: '0.8rem', color: '#fbbf24', fontWeight: 600, textTransform: 'uppercase', marginBottom: '0.25rem' }}>
                      Reason Approval Is Required
                    </div>
                    <div style={{ fontSize: '0.92rem', color: '#fef3c7' }}>
                      This task requires explicit operator verification before executing actions in the environment.
                    </div>
                  </div>

                  {/* Risks assessment */}
                  {context.risks && context.risks.length > 0 && (
                    <div style={{ backgroundColor: 'rgba(239, 68, 68, 0.05)', padding: '0.9rem 1rem', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                      <div style={{ fontSize: '0.8rem', color: '#f87171', fontWeight: 600, textTransform: 'uppercase', marginBottom: '0.35rem' }}>
                        Risk & Impact Evaluation
                      </div>
                      <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.88rem', color: '#fecaca' }}>
                        {context.risks.map((risk, idx) => (
                          <li key={idx} style={{ marginBottom: '0.2rem' }}>{risk}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Upstream Dependencies */}
                  <div>
                    <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
                      Upstream Prerequisites ({context.upstream_dependencies.length})
                    </div>
                    {context.upstream_dependencies.length === 0 ? (
                      <div style={{ fontSize: '0.85rem', color: '#64748b', fontStyle: 'italic' }}>
                        No upstream dependencies. Ready for direct execution.
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        {context.upstream_dependencies.map((dep) => (
                          <div
                            key={dep.task_id}
                            style={{
                              padding: '0.75rem',
                              borderRadius: '6px',
                              backgroundColor: 'rgba(255, 255, 255, 0.02)',
                              border: '1px solid rgba(255, 255, 255, 0.05)',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '0.35rem',
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontSize: '0.9rem', fontWeight: 500, color: '#f1f5f9' }}>
                                {dep.title}
                              </span>
                              <span
                                style={{
                                  fontSize: '0.75rem',
                                  padding: '0.15rem 0.5rem',
                                  borderRadius: '4px',
                                  backgroundColor: dep.is_completed ? 'rgba(34, 197, 94, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                                  color: dep.is_completed ? '#4ade80' : '#fbbf24',
                                }}
                              >
                                {dep.status.toUpperCase()}
                              </span>
                            </div>
                            {dep.latest_output_preview && (
                              <div style={{ fontSize: '0.8rem', color: '#94a3b8', fontFamily: 'monospace', backgroundColor: 'rgba(0,0,0,0.3)', padding: '0.4rem', borderRadius: '4px' }}>
                                {dep.latest_output_preview}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Approval Note */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                    <label style={{ fontSize: '0.82rem', color: '#94a3b8' }}>
                      Operator Note (Audit Log):
                    </label>
                    <input
                      type="text"
                      value={approvalReason}
                      onChange={(e) => setApprovalReason(e.target.value)}
                      style={{
                        backgroundColor: '#1a1d24',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        borderRadius: '6px',
                        padding: '0.6rem 0.75rem',
                        color: '#f8fafc',
                        fontSize: '0.9rem',
                      }}
                    />
                  </div>
                </div>
              )}

              {/* View 2: Reject Form */}
              {view === 'reject' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <div style={{ fontSize: '1rem', fontWeight: 600, color: '#f87171' }}>
                    Reject Task Execution
                  </div>
                  <p style={{ fontSize: '0.9rem', color: '#cbd5e1', margin: 0 }}>
                    Please explain why this task is being rejected. This reason will be recorded in the audit log and any downstream tasks will be marked as blocked.
                  </p>
                  <textarea
                    rows={4}
                    placeholder="Provide specific reason (e.g. Unsafe architectural pattern, criteria mismatch)..."
                    value={rejectionReason}
                    onChange={(e) => setRejectionReason(e.target.value)}
                    style={{
                      backgroundColor: '#1a1d24',
                      border: '1px solid rgba(239, 68, 68, 0.4)',
                      borderRadius: '6px',
                      padding: '0.75rem',
                      color: '#f8fafc',
                      fontSize: '0.9rem',
                      fontFamily: 'inherit',
                    }}
                  />
                </div>
              )}

              {/* View 3: Edit & Resubmit Form */}
              {view === 'edit' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <div style={{ fontSize: '1rem', fontWeight: 600, color: '#60a5fa' }}>
                    Edit & Resubmit Task
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                    <label style={{ fontSize: '0.82rem', color: '#94a3b8' }}>Title</label>
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      style={{
                        backgroundColor: '#1a1d24',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        borderRadius: '6px',
                        padding: '0.6rem 0.75rem',
                        color: '#f8fafc',
                      }}
                    />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                    <label style={{ fontSize: '0.82rem', color: '#94a3b8' }}>Instructions / Description</label>
                    <textarea
                      rows={3}
                      value={editDescription}
                      onChange={(e) => setEditDescription(e.target.value)}
                      style={{
                        backgroundColor: '#1a1d24',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        borderRadius: '6px',
                        padding: '0.6rem 0.75rem',
                        color: '#f8fafc',
                        fontFamily: 'inherit',
                      }}
                    />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                    <label style={{ fontSize: '0.82rem', color: '#94a3b8' }}>Acceptance Criteria</label>
                    <textarea
                      rows={2}
                      value={editCriteria}
                      onChange={(e) => setEditCriteria(e.target.value)}
                      style={{
                        backgroundColor: '#1a1d24',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        borderRadius: '6px',
                        padding: '0.6rem 0.75rem',
                        color: '#f8fafc',
                        fontFamily: 'inherit',
                      }}
                    />
                  </div>
                </div>
              )}
            </>
          ) : null}
        </div>

        {/* Footer Actions */}
        <div
          style={{
            padding: '1.25rem 1.5rem',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor: '#0c0e12',
          }}
        >
          {view === 'overview' ? (
            <>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setView('edit')}
                  disabled={submitting}
                  style={{
                    backgroundColor: 'transparent',
                    border: '1px solid rgba(255, 255, 255, 0.2)',
                    color: '#94a3b8',
                    padding: '0.6rem 1rem',
                    borderRadius: '6px',
                    fontSize: '0.88rem',
                    cursor: 'pointer',
                  }}
                >
                  Edit & Resubmit
                </button>
                <button
                  type="button"
                  onClick={() => setView('reject')}
                  disabled={submitting}
                  style={{
                    backgroundColor: 'rgba(239, 68, 68, 0.15)',
                    border: '1px solid rgba(239, 68, 68, 0.4)',
                    color: '#fca5a5',
                    padding: '0.6rem 1rem',
                    borderRadius: '6px',
                    fontSize: '0.88rem',
                    cursor: 'pointer',
                  }}
                >
                  Reject
                </button>
              </div>

              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <button
                  type="button"
                  onClick={onClose}
                  disabled={submitting}
                  style={{
                    backgroundColor: 'transparent',
                    border: 'none',
                    color: '#94a3b8',
                    padding: '0.6rem 1rem',
                    borderRadius: '6px',
                    fontSize: '0.88rem',
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleApprove}
                  disabled={submitting || (context ? !context.dependencies_all_completed : false)}
                  style={{
                    backgroundColor: context?.dependencies_all_completed ? '#10b981' : '#64748b',
                    border: 'none',
                    color: '#ffffff',
                    fontWeight: 600,
                    padding: '0.6rem 1.4rem',
                    borderRadius: '6px',
                    fontSize: '0.9rem',
                    cursor: context?.dependencies_all_completed ? 'pointer' : 'not-allowed',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    boxShadow: context?.dependencies_all_completed ? '0 0 15px rgba(16, 185, 129, 0.4)' : 'none',
                  }}
                >
                  {submitting ? 'Executing...' : 'Approve & Execute'}
                </button>
              </div>
            </>
          ) : view === 'reject' ? (
            <>
              <button
                type="button"
                onClick={() => setView('overview')}
                disabled={submitting}
                style={{
                  backgroundColor: 'transparent',
                  border: '1px solid rgba(255, 255, 255, 0.2)',
                  color: '#94a3b8',
                  padding: '0.6rem 1rem',
                  borderRadius: '6px',
                  cursor: 'pointer',
                }}
              >
                Back
              </button>
              <button
                type="button"
                onClick={handleReject}
                disabled={submitting || !rejectionReason.trim()}
                style={{
                  backgroundColor: '#ef4444',
                  border: 'none',
                  color: '#ffffff',
                  fontWeight: 600,
                  padding: '0.6rem 1.4rem',
                  borderRadius: '6px',
                  cursor: rejectionReason.trim() ? 'pointer' : 'not-allowed',
                }}
              >
                {submitting ? 'Rejecting...' : 'Confirm Rejection'}
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={() => setView('overview')}
                disabled={submitting}
                style={{
                  backgroundColor: 'transparent',
                  border: '1px solid rgba(255, 255, 255, 0.2)',
                  color: '#94a3b8',
                  padding: '0.6rem 1rem',
                  borderRadius: '6px',
                  cursor: 'pointer',
                }}
              >
                Back
              </button>
              <button
                type="button"
                onClick={handleEditAndResubmit}
                disabled={submitting || !editTitle.trim()}
                style={{
                  backgroundColor: '#3b82f6',
                  border: 'none',
                  color: '#ffffff',
                  fontWeight: 600,
                  padding: '0.6rem 1.4rem',
                  borderRadius: '6px',
                  cursor: editTitle.trim() ? 'pointer' : 'not-allowed',
                }}
              >
                {submitting ? 'Saving...' : 'Save & Resubmit'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
