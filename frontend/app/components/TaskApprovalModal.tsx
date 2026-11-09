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
          backgroundColor: '#161B22',
          border: '1px solid #2A313C',
          boxShadow: '0 20px 40px rgba(0, 0, 0, 0.6)',
          borderRadius: '8px',
          width: '100%',
          maxWidth: '720px',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          color: '#E6EDF3',
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
            backgroundColor: '#161B22',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span
              style={{
                display: 'inline-block',
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#f5b841',
              }}
            />
            <h2
              id="approval-modal-title"
              style={{ fontSize: '1rem', fontWeight: 600, margin: 0, color: '#E6EDF3' }}
            >
              Task governance review
            </h2>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 500,
                padding: '0.15rem 0.5rem',
                borderRadius: '4px',
                backgroundColor: '#261B0E',
                color: '#FDE68A',
                border: '1px solid #6E4919',
              }}
            >
              Awaiting approval
            </span>
          </div>
          <button
            onClick={onClose}
            aria-label="Close modal"
            style={{
              background: 'transparent',
              border: 'none',
              color: '#8B949E',
              fontSize: '1.1rem',
              cursor: 'pointer',
              padding: '0.25rem',
              lineHeight: 1,
            }}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '1.25rem', overflowY: 'auto', flex: 1 }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '2rem', color: '#8B949E' }}>
              Loading task approval context...
            </div>
          ) : error && !context ? (
            <div style={{ padding: '0.75rem 1rem', backgroundColor: '#291013', color: '#FCA5A5', border: '1px solid #66242B', borderRadius: '6px' }}>
              {error}
            </div>
          ) : context ? (
            <>
              {error && (
                <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', backgroundColor: '#291013', color: '#FCA5A5', border: '1px solid #66242B', borderRadius: '6px', fontSize: '0.85rem' }}>
                  {error}
                </div>
              )}

              {/* View 1: Overview & Decision */}
              {view === 'overview' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {/* Task Objective */}
                  <div style={{ backgroundColor: '#0E1116', padding: '1rem', borderRadius: '6px', border: '1px solid #2A313C' }}>
                    <div style={{ fontSize: '0.75rem', color: '#8B949E', marginBottom: '0.25rem' }}>
                      Task objective
                    </div>
                    <div style={{ fontSize: '1rem', fontWeight: 600, color: '#E6EDF3' }}>
                      {context.title}
                    </div>
                    {context.description && (
                      <p style={{ marginTop: '0.5rem', fontSize: '0.875rem', color: '#8B949E', lineHeight: 1.5 }}>
                        {context.description}
                      </p>
                    )}
                    <div style={{ display: 'flex', gap: '1rem', marginTop: '0.75rem', fontSize: '0.8rem' }}>
                      <span style={{ color: '#8B949E' }}>
                        Type: <strong style={{ color: '#E6EDF3', fontWeight: 500 }}>{context.task_type}</strong>
                      </span>
                      <span style={{ color: '#8B949E' }}>
                        Priority: <strong style={{ color: '#E6EDF3', fontWeight: 500, fontVariantNumeric: 'tabular-nums' }}>{context.priority}/10</strong>
                      </span>
                      {context.assigned_provider && (
                        <span style={{ color: '#8B949E' }}>
                          Model: <strong style={{ color: '#E6EDF3', fontWeight: 500 }}>{context.assigned_provider} / {context.assigned_model}</strong>
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Reason approval required */}
                  <div style={{ backgroundColor: '#261B0E', padding: '0.75rem 1rem', borderRadius: '6px', border: '1px solid #6E4919' }}>
                    <div style={{ fontSize: '0.75rem', color: '#FDE68A', fontWeight: 600, marginBottom: '0.25rem' }}>
                      Reason approval is required
                    </div>
                    <div style={{ fontSize: '0.85rem', color: '#FDE68A' }}>
                      This task requires explicit operator verification before executing actions in the environment.
                    </div>
                  </div>

                  {/* Risks assessment */}
                  {context.risks && context.risks.length > 0 && (
                    <div style={{ backgroundColor: '#291013', padding: '0.75rem 1rem', borderRadius: '6px', border: '1px solid #66242B' }}>
                      <div style={{ fontSize: '0.75rem', color: '#FCA5A5', fontWeight: 600, marginBottom: '0.35rem' }}>
                        Risk and impact evaluation
                      </div>
                      <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.85rem', color: '#FCA5A5' }}>
                        {context.risks.map((risk, idx) => (
                          <li key={idx} style={{ marginBottom: '0.2rem' }}>{risk}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Upstream Dependencies */}
                  <div>
                    <div style={{ fontSize: '0.75rem', fontWeight: 500, color: '#8B949E', marginBottom: '0.5rem' }}>
                      Upstream prerequisites ({context.upstream_dependencies.length})
                    </div>
                    {context.upstream_dependencies.length === 0 ? (
                      <div style={{ fontSize: '0.85rem', color: '#8B949E', fontStyle: 'italic' }}>
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
                              backgroundColor: '#0E1116',
                              border: '1px solid #2A313C',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '0.35rem',
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontSize: '0.875rem', fontWeight: 500, color: '#E6EDF3' }}>
                                {dep.title}
                              </span>
                              <span
                                style={{
                                  fontSize: '0.75rem',
                                  padding: '0.15rem 0.5rem',
                                  borderRadius: '4px',
                                  backgroundColor: dep.is_completed ? '#0E2318' : '#261B0E',
                                  color: dep.is_completed ? '#86EFAC' : '#FDE68A',
                                  border: `1px solid ${dep.is_completed ? '#1D5A38' : '#6E4919'}`,
                                }}
                              >
                                {dep.status}
                              </span>
                            </div>
                            {dep.latest_output_preview && (
                              <div style={{ fontSize: '0.8rem', color: '#8B949E', fontFamily: 'monospace', backgroundColor: '#161B22', padding: '0.4rem', borderRadius: '4px' }}>
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
                    <label style={{ fontSize: '0.8rem', color: '#8B949E' }}>
                      Operator note (audit log)
                    </label>
                    <input
                      type="text"
                      value={approvalReason}
                      onChange={(e) => setApprovalReason(e.target.value)}
                      style={{
                        backgroundColor: '#0E1116',
                        border: '1px solid #2A313C',
                        borderRadius: '6px',
                        padding: '0.5rem 0.75rem',
                        color: '#E6EDF3',
                        fontSize: '0.875rem',
                      }}
                    />
                  </div>
                </div>
              )}

              {/* View 2: Reject Form */}
              {view === 'reject' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <div style={{ fontSize: '0.95rem', fontWeight: 600, color: '#FCA5A5' }}>
                    Reject task execution
                  </div>
                  <p style={{ fontSize: '0.875rem', color: '#8B949E', margin: 0 }}>
                    Provide a specific reason for rejection. This reason will be recorded in the audit log and any downstream tasks will be marked as blocked.
                  </p>
                  <textarea
                    rows={4}
                    placeholder="Provide specific reason (e.g. Unsafe architectural pattern, criteria mismatch)..."
                    value={rejectionReason}
                    onChange={(e) => setRejectionReason(e.target.value)}
                    style={{
                      backgroundColor: '#0E1116',
                      border: '1px solid #66242B',
                      borderRadius: '6px',
                      padding: '0.6rem 0.75rem',
                      color: '#E6EDF3',
                      fontSize: '0.875rem',
                      fontFamily: 'inherit',
                    }}
                  />
                </div>
              )}

              {/* View 3: Edit & Resubmit Form */}
              {view === 'edit' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <div style={{ fontSize: '0.95rem', fontWeight: 600, color: '#E6EDF3' }}>
                    Edit and resubmit task
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <label style={{ fontSize: '0.8rem', color: '#8B949E' }}>Title</label>
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      style={{
                        backgroundColor: '#0E1116',
                        border: '1px solid #2A313C',
                        borderRadius: '6px',
                        padding: '0.5rem 0.75rem',
                        color: '#E6EDF3',
                        fontSize: '0.875rem',
                      }}
                    />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <label style={{ fontSize: '0.8rem', color: '#8B949E' }}>Instructions / description</label>
                    <textarea
                      rows={3}
                      value={editDescription}
                      onChange={(e) => setEditDescription(e.target.value)}
                      style={{
                        backgroundColor: '#0E1116',
                        border: '1px solid #2A313C',
                        borderRadius: '6px',
                        padding: '0.5rem 0.75rem',
                        color: '#E6EDF3',
                        fontFamily: 'inherit',
                        fontSize: '0.875rem',
                      }}
                    />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <label style={{ fontSize: '0.8rem', color: '#8B949E' }}>Acceptance criteria</label>
                    <textarea
                      rows={2}
                      value={editCriteria}
                      onChange={(e) => setEditCriteria(e.target.value)}
                      style={{
                        backgroundColor: '#0E1116',
                        border: '1px solid #2A313C',
                        borderRadius: '6px',
                        padding: '0.5rem 0.75rem',
                        color: '#E6EDF3',
                        fontFamily: 'inherit',
                        fontSize: '0.875rem',
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
            padding: '1rem 1.25rem',
            borderTop: '1px solid #2A313C',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor: '#0E1116',
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
                    border: '1px solid #2A313C',
                    color: '#8B949E',
                    padding: '0.5rem 0.75rem',
                    borderRadius: '6px',
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                  }}
                >
                  Edit and resubmit
                </button>
                <button
                  type="button"
                  onClick={() => setView('reject')}
                  disabled={submitting}
                  style={{
                    backgroundColor: '#291013',
                    border: '1px solid #66242B',
                    color: '#FCA5A5',
                    padding: '0.5rem 0.75rem',
                    borderRadius: '6px',
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                  }}
                >
                  Reject
                </button>
              </div>

              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  type="button"
                  onClick={onClose}
                  disabled={submitting}
                  style={{
                    backgroundColor: 'transparent',
                    border: 'none',
                    color: '#8B949E',
                    padding: '0.5rem 0.75rem',
                    borderRadius: '6px',
                    fontSize: '0.85rem',
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
                    backgroundColor: context?.dependencies_all_completed ? '#f5b841' : '#2A313C',
                    border: 'none',
                    color: context?.dependencies_all_completed ? '#0E1116' : '#8B949E',
                    fontWeight: 600,
                    padding: '0.5rem 1rem',
                    borderRadius: '6px',
                    fontSize: '0.85rem',
                    cursor: context?.dependencies_all_completed ? 'pointer' : 'not-allowed',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                  }}
                >
                  {submitting ? 'Executing...' : 'Approve and execute'}
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
                  border: '1px solid #2A313C',
                  color: '#8B949E',
                  padding: '0.5rem 0.75rem',
                  borderRadius: '6px',
                  fontSize: '0.85rem',
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
                  padding: '0.5rem 1rem',
                  borderRadius: '6px',
                  fontSize: '0.85rem',
                  cursor: rejectionReason.trim() ? 'pointer' : 'not-allowed',
                  opacity: rejectionReason.trim() ? 1 : 0.6,
                }}
              >
                {submitting ? 'Rejecting...' : 'Confirm rejection'}
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
                  border: '1px solid #2A313C',
                  color: '#8B949E',
                  padding: '0.5rem 0.75rem',
                  borderRadius: '6px',
                  fontSize: '0.85rem',
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
                  backgroundColor: '#f5b841',
                  border: 'none',
                  color: '#0E1116',
                  fontWeight: 600,
                  padding: '0.5rem 1rem',
                  borderRadius: '6px',
                  fontSize: '0.85rem',
                  cursor: editTitle.trim() ? 'pointer' : 'not-allowed',
                  opacity: editTitle.trim() ? 1 : 0.6,
                }}
              >
                {submitting ? 'Saving...' : 'Save and resubmit'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
