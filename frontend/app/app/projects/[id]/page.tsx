'use client';

import React, { useEffect, useRef, useState, use } from 'react';
import {
  memoryApi,
  MemoryGraphData,
  Project,
  projectsApi,
  Task,
  TaskDetail,
  tasksApi,
} from '@/lib/api';
import { SynqWebSocket, WebSocketEvent } from '@/lib/ws';
import DagCanvas from '@/app/components/DagCanvas';
import TaskApprovalModal from '@/app/components/TaskApprovalModal';
import ExportModal from '@/app/components/ExportModal';

export default function ProjectWorkspacePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);
  const projectId = resolvedParams.id;

  const [project, setProject] = useState<Project | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [activeTab, setActiveTab] = useState<'board' | 'dag' | 'planner' | 'memory'>('board');
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [selectedTaskDetail, setSelectedTaskDetail] = useState<TaskDetail | null>(null);
  const [loading, setLoading] = useState(true);

  // Live Token Streaming
  const [liveStreamOutput, setLiveStreamOutput] = useState<string>('');
  const [executingTaskId, setExecutingTaskId] = useState<string | null>(null);

  // Approval Modal State
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [approvalTaskId, setApprovalTaskId] = useState<string | null>(null);

  // Export Deliverables Modal State
  const [showExportModal, setShowExportModal] = useState(false);

  // Create Task Form
  const [showAddTaskModal, setShowAddTaskModal] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskDesc, setNewTaskDesc] = useState('');
  const [newTaskType, setNewTaskType] = useState('code');
  const [newTaskPriority, setNewTaskPriority] = useState(7);
  const [newTaskApproval, setNewTaskApproval] = useState(false);

  // AI Planner Form
  const [plannerGoal, setPlannerGoal] = useState('');
  const [planning, setPlanning] = useState(false);
  const [planSuccessMsg, setPlanSuccessMsg] = useState<string | null>(null);
  const [planErrorMsg, setPlanErrorMsg] = useState<string | null>(null);

  // Memory Graph
  const [memoryGraph, setMemoryGraph] = useState<MemoryGraphData | null>(null);
  const [selectedGraphNode, setSelectedGraphNode] = useState<any | null>(null);

  // WebSocket reference
  const wsRef = useRef<SynqWebSocket | null>(null);
  const selectedTaskIdRef = useRef<string | null>(null);

  const loadProjectAndTasks = async () => {
    try {
      const [proj, taskList] = await Promise.all([
        projectsApi.get(projectId),
        tasksApi.list(projectId),
      ]);
      setProject(proj);
      setTasks(taskList);
      if (taskList.length > 0 && !selectedTaskId) {
        setSelectedTaskId(taskList[0].id);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadTaskDetail = async (taskId: string) => {
    try {
      const detail = await tasksApi.getDetail(taskId);
      setSelectedTaskDetail(detail);
    } catch (err) {
      console.error(err);
    }
  };

  const loadMemoryGraph = async () => {
    try {
      const graph = await memoryApi.getGraph(projectId);
      setMemoryGraph(graph);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadProjectAndTasks();
    loadMemoryGraph();

    // Initialize live WebSocket stream
    const ws = new SynqWebSocket(projectId);
    wsRef.current = ws;

    const unsubscribe = ws.subscribe((event: WebSocketEvent) => {
      if (event.event_type === 'task_token') {
        setLiveStreamOutput((prev) => prev + event.data.token);
      } else if (event.event_type === 'task_started') {
        setExecutingTaskId(event.data.task_id);
        setLiveStreamOutput('');
        loadProjectAndTasks();
      } else if (
        event.event_type === 'task_completed' ||
        event.event_type === 'task_failed' ||
        event.event_type === 'task_approved' ||
        event.event_type === 'task_rejected' ||
        event.event_type === 'task_awaiting_approval' ||
        event.event_type === 'dependency_added' ||
        event.event_type === 'dependency_removed' ||
        event.event_type === 'task_review_completed'
      ) {
        setExecutingTaskId(null);
        loadProjectAndTasks();
        loadMemoryGraph();
        if (selectedTaskIdRef.current) {
          loadTaskDetail(selectedTaskIdRef.current);
        }
      }
    });

    return () => {
      unsubscribe();
      ws.destroy();
    };
  }, [projectId]);

  useEffect(() => {
    selectedTaskIdRef.current = selectedTaskId;
    if (selectedTaskId) {
      loadTaskDetail(selectedTaskId);
      setLiveStreamOutput('');
    }
  }, [selectedTaskId]);

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskTitle.trim()) return;
    try {
      await tasksApi.create(projectId, {
        title: newTaskTitle,
        description: newTaskDesc.trim() || undefined,
        task_type: newTaskType,
        priority: newTaskPriority,
        requires_approval: newTaskApproval,
      });
      setNewTaskTitle('');
      setNewTaskDesc('');
      setShowAddTaskModal(false);
      await loadProjectAndTasks();
    } catch (err: any) {
      alert(err.message || 'Failed to create task');
    }
  };

  const handleExecuteTask = async (taskId: string) => {
    try {
      setExecutingTaskId(taskId);
      setLiveStreamOutput('');
      await tasksApi.execute(taskId);
      await loadProjectAndTasks();
      await loadTaskDetail(taskId);
    } catch (err: any) {
      alert(err.message || 'Execution error');
      setExecutingTaskId(null);
    }
  };

  const handleRunPlanner = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!plannerGoal.trim()) return;
    try {
      setPlanning(true);
      setPlanSuccessMsg(null);
      setPlanErrorMsg(null);
      const res = await tasksApi.plan(projectId, plannerGoal, project?.domain);
      setPlanSuccessMsg(`Decomposed goal into ${res.task_count} subtasks.`);
      setPlannerGoal('');
      await loadProjectAndTasks();
      setActiveTab('dag');
    } catch (err: any) {
      setPlanErrorMsg(err.message || 'Planning failed');
    } finally {
      setPlanning(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0', color: 'var(--text-muted)' }}>
        Loading project workspace...
      </div>
    );
  }

  if (!project) {
    return (
      <div className="glass-panel" style={{ padding: '60px', textAlign: 'center' }}>
        <h3>Project not found</h3>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* ── Project Header ──────────────────────────────────────────────── */}
      <div
        className="glass-panel"
        style={{
          padding: '24px 32px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '20px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <h1 className="font-serif" style={{ fontSize: '1.75rem', color: '#E6EDF3', margin: 0, fontWeight: 600 }}>
              {project.name}
            </h1>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 500,
                padding: '2px 8px',
                borderRadius: '4px',
                background: '#1F242C',
                color: '#E6EDF3',
                border: '1px solid #2A313C',
              }}
            >
              {project.domain}
            </span>
            <span className={`badge badge-${project.status}`}>{project.status}</span>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', maxWidth: '700px', margin: 0 }}>
            {project.description || 'No description provided.'}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <button
            onClick={() => setShowExportModal(true)}
            className="btn-secondary"
            style={{ padding: '8px 16px', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            Export deliverables
          </button>
          <button
            onClick={() => setActiveTab('planner')}
            className="btn-secondary"
            style={{ padding: '8px 16px', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
            </svg>
            AI planner
          </button>
          <button
            onClick={() => setShowAddTaskModal(true)}
            className="btn-primary"
            style={{ padding: '8px 16px', fontSize: '0.85rem' }}
          >
            + Add task
          </button>
        </div>
      </div>

      {/* ── Tab Switcher ────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '12px', flexWrap: 'wrap' }}>
        <button
          onClick={() => setActiveTab('board')}
          style={{
            padding: '6px 14px',
            borderRadius: '6px',
            fontWeight: 500,
            fontSize: '0.85rem',
            background: activeTab === 'board' ? '#161B22' : 'transparent',
            color: activeTab === 'board' ? '#E6EDF3' : 'var(--text-muted)',
            border: activeTab === 'board' ? '1px solid #2A313C' : '1px solid transparent',
            cursor: 'pointer',
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          Task board ({tasks.length})
        </button>

        <button
          onClick={() => setActiveTab('dag')}
          style={{
            padding: '6px 14px',
            borderRadius: '6px',
            fontWeight: 500,
            fontSize: '0.85rem',
            background: activeTab === 'dag' ? '#161B22' : 'transparent',
            color: activeTab === 'dag' ? '#E6EDF3' : 'var(--text-muted)',
            border: activeTab === 'dag' ? '1px solid #2A313C' : '1px solid transparent',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <rect x="3" y="3" width="6" height="6" rx="1" />
            <rect x="15" y="15" width="6" height="6" rx="1" />
            <path d="M9 6h6v9" />
          </svg>
          DAG canvas
        </button>

        <button
          onClick={() => {
            setActiveTab('memory');
            loadMemoryGraph();
          }}
          style={{
            padding: '6px 14px',
            borderRadius: '6px',
            fontWeight: 500,
            fontSize: '0.85rem',
            background: activeTab === 'memory' ? '#161B22' : 'transparent',
            color: activeTab === 'memory' ? '#E6EDF3' : 'var(--text-muted)',
            border: activeTab === 'memory' ? '1px solid #2A313C' : '1px solid transparent',
            cursor: 'pointer',
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          Memory graph ({memoryGraph?.nodes.length || 0})
        </button>

        <button
          onClick={() => setActiveTab('planner')}
          style={{
            padding: '6px 14px',
            borderRadius: '6px',
            fontWeight: 500,
            fontSize: '0.85rem',
            background: activeTab === 'planner' ? '#161B22' : 'transparent',
            color: activeTab === 'planner' ? '#E6EDF3' : 'var(--text-muted)',
            border: activeTab === 'planner' ? '1px solid #2A313C' : '1px solid transparent',
            cursor: 'pointer',
          }}
        >
          AI planner
        </button>
      </div>

      {/* ── TAB 1: TASK BOARD & MONITOR ─────────────────────────────────── */}
      {activeTab === 'board' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.3fr', gap: '20px', alignItems: 'start' }}>
          {/* Left Column: Task List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {tasks.length === 0 ? (
              <div className="glass-panel" style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
                No tasks yet. Use <strong>+ Add task</strong> or the <strong>AI planner</strong> to decompose goals.
              </div>
            ) : (
              tasks.map((task, idx) => {
                const isSelected = selectedTaskId === task.id;
                const isExecuting = executingTaskId === task.id;
                const isAwaitingApproval = task.status === 'awaiting_approval';
                const isRejected = task.status === 'rejected';

                return (
                  <div
                    key={task.id}
                    onClick={() => setSelectedTaskId(task.id)}
                    className="glass-panel"
                    style={{
                      padding: '12px 16px',
                      cursor: 'pointer',
                      borderColor: isSelected
                        ? '#F5B841'
                        : isAwaitingApproval
                        ? '#6E4919'
                        : isRejected
                        ? '#66242B'
                        : '#2A313C',
                      background: isSelected
                        ? 'rgba(245, 184, 65, 0.05)'
                        : '#161B22',
                      transition: 'border-color 0.12s ease',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#8B949E', fontFamily: 'monospace', fontVariantNumeric: 'tabular-nums' }}>
                          #{idx + 1}
                        </span>
                        <span
                          style={{
                            fontSize: '0.7rem',
                            padding: '2px 6px',
                            borderRadius: '3px',
                            fontFamily: 'monospace',
                            background: '#1F242C',
                            color: '#8B949E',
                            border: '1px solid #2A313C',
                          }}
                        >
                          {task.task_type}
                        </span>
                      </div>
                      <span className={`badge badge-${task.status}`}>
                        {isExecuting && <span className="pulse-dot"></span>}
                        {task.status}
                      </span>
                    </div>

                    <h4 style={{ fontSize: '0.92rem', fontWeight: 600, color: '#E6EDF3', marginBottom: '4px' }}>{task.title}</h4>

                    {isAwaitingApproval && (
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px', borderTop: '1px solid #2A313C', paddingTop: '8px' }}>
                        <span style={{ fontSize: '0.75rem', color: '#F5B841' }}>
                          Approval required
                        </span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setApprovalTaskId(task.id);
                            setShowApprovalModal(true);
                          }}
                          className="btn-primary"
                          style={{
                            padding: '3px 8px',
                            fontSize: '0.75rem',
                            background: '#F5B841',
                            color: '#0E1116',
                            fontWeight: 600,
                          }}
                        >
                          Review and approve
                        </button>
                      </div>
                    )}

                    {isRejected && task.rejection_reason && (
                      <div style={{ fontSize: '0.75rem', color: '#FCA5A5', marginTop: '6px' }}>
                        Rejection reason: {task.rejection_reason}
                      </div>
                    )}

                    {task.dependencies.length > 0 && (
                      <div style={{ fontSize: '0.75rem', color: '#8B949E', marginTop: '4px', fontVariantNumeric: 'tabular-nums' }}>
                        Depends on: {task.dependencies.length} tasks
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>

          {/* Right Column: Execution Monitor & Detail */}
          <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px', background: '#161B22', border: '1px solid #2A313C' }}>
            {selectedTaskDetail ? (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <span
                      style={{
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        color: '#F5B841',
                        letterSpacing: '0.02em',
                      }}
                    >
                      Task inspector
                    </span>
                    <h2 style={{ fontSize: '1.25rem', color: '#E6EDF3', marginTop: '4px', fontWeight: 600 }}>
                      {selectedTaskDetail.title}
                    </h2>
                  </div>

                  <div style={{ display: 'flex', gap: '8px' }}>
                    {selectedTaskDetail.status === 'awaiting_approval' && (
                      <button
                        onClick={() => {
                          setApprovalTaskId(selectedTaskDetail.id);
                          setShowApprovalModal(true);
                        }}
                        className="btn-primary"
                        style={{ padding: '6px 14px', fontSize: '0.85rem', background: '#F5B841', color: '#0E1116', fontWeight: 600 }}
                      >
                        Review and approve
                      </button>
                    )}

                    {selectedTaskDetail.status === 'rejected' && (
                      <button
                        onClick={() => {
                          setApprovalTaskId(selectedTaskDetail.id);
                          setShowApprovalModal(true);
                        }}
                        className="btn-secondary"
                        style={{ padding: '6px 14px', fontSize: '0.85rem', color: '#FCA5A5', borderColor: '#66242B' }}
                      >
                        Edit and resubmit
                      </button>
                    )}

                    {selectedTaskDetail.status !== 'awaiting_approval' && selectedTaskDetail.status !== 'rejected' && (
                      <button
                        onClick={() => handleExecuteTask(selectedTaskDetail.id)}
                        disabled={executingTaskId === selectedTaskDetail.id || selectedTaskDetail.status === 'blocked'}
                        className="btn-primary"
                        style={{ padding: '6px 16px', fontSize: '0.85rem' }}
                      >
                        {executingTaskId === selectedTaskDetail.id ? 'Running agent...' : 'Run task'}
                      </button>
                    )}
                  </div>
                </div>

                <div style={{ fontSize: '0.875rem', color: '#8B949E', lineHeight: 1.5 }}>
                  {selectedTaskDetail.description || 'No specific instructions provided.'}
                </div>

                {selectedTaskDetail.approval_reason && (
                  <div
                    style={{
                      padding: '10px 14px',
                      background: '#0E2318',
                      borderRadius: '6px',
                      borderLeft: '3px solid #1D5A38',
                      fontSize: '0.85rem',
                      color: '#86EFAC',
                    }}
                  >
                    <strong style={{ color: '#E6EDF3', fontWeight: 600 }}>Operator approval:</strong> {selectedTaskDetail.approval_reason} (Approved by: {selectedTaskDetail.approved_by || 'Human Operator'})
                  </div>
                )}

                {selectedTaskDetail.rejection_reason && (
                  <div
                    style={{
                      padding: '10px 14px',
                      background: '#291013',
                      borderRadius: '6px',
                      borderLeft: '3px solid #66242B',
                      fontSize: '0.85rem',
                      color: '#FCA5A5',
                    }}
                  >
                    <strong style={{ color: '#E6EDF3', fontWeight: 600 }}>Rejection notice:</strong> {selectedTaskDetail.rejection_reason}
                  </div>
                )}

                {selectedTaskDetail.acceptance_criteria && (
                  <div
                    style={{
                      padding: '10px 14px',
                      background: '#161B22',
                      borderRadius: '6px',
                      borderLeft: '3px solid #F5B841',
                      borderTop: '1px solid #2A313C',
                      borderRight: '1px solid #2A313C',
                      borderBottom: '1px solid #2A313C',
                      fontSize: '0.85rem',
                      color: '#E6EDF3',
                    }}
                  >
                    <strong style={{ color: '#F5B841', fontWeight: 600 }}>Acceptance criteria:</strong> {selectedTaskDetail.acceptance_criteria}
                  </div>
                )}

                {/* Real-time Streaming Output / Output Box */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#8B949E', letterSpacing: '0.02em' }}>
                      Agent output {executingTaskId === selectedTaskDetail.id && '(live stream)'}
                    </span>
                    {executingTaskId === selectedTaskDetail.id && (
                      <span style={{ fontSize: '0.75rem', color: '#67E8F9', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span className="pulse-dot"></span> Streaming tokens via WebSocket
                      </span>
                    )}
                  </div>

                  <div
                    style={{
                      background: '#0E1116',
                      border: '1px solid #2A313C',
                      borderRadius: '6px',
                      padding: '14px',
                      minHeight: '180px',
                      maxHeight: '340px',
                      overflowY: 'auto',
                      fontFamily: 'monospace',
                      fontSize: '0.82rem',
                      lineHeight: 1.5,
                      color: '#E6EDF3',
                      whiteSpace: 'pre-wrap',
                    }}
                  >
                    {executingTaskId === selectedTaskDetail.id
                      ? (liveStreamOutput ? liveStreamOutput + ' ▋' : 'Routing to optimal low-latency agent...')
                      : selectedTaskDetail.executions.length > 0 && selectedTaskDetail.executions[0].output
                      ? selectedTaskDetail.executions[0].output
                      : selectedTaskDetail.executions.length > 0 && selectedTaskDetail.executions[0].error_message
                      ? `Execution failed: ${selectedTaskDetail.executions[0].error_message}`
                      : 'No execution output yet. Click "Run task" to trigger routing and execution.'}
                  </div>
                </div>

                {/* Routing & Execution History */}
                {selectedTaskDetail.executions.length > 0 && (
                  <div style={{ borderTop: '1px solid #2A313C', paddingTop: '16px' }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#8B949E', letterSpacing: '0.02em', marginBottom: '10px' }}>
                      Routing decision and quality audit
                    </div>
                    {selectedTaskDetail.executions.map((ex) => {
                      const reviewData = ex.validation_result?.collaborative_review;

                      return (
                        <div
                          key={ex.id}
                          style={{
                            padding: '12px 14px',
                            background: '#0E1116',
                            border: '1px solid #2A313C',
                            borderRadius: '6px',
                            marginBottom: '8px',
                            fontSize: '0.85rem',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                            <span>
                              Attempt #{ex.attempt}: <strong style={{ color: '#E6EDF3', fontWeight: 500 }}>{ex.provider_id}:{ex.model_id}</strong>
                            </span>
                            <span style={{ color: ex.validation_passed ? '#86EFAC' : '#FCA5A5' }}>
                              {ex.validation_passed
                                ? 'Validation passed'
                                : ex.error_message
                                ? 'Execution failed'
                                : 'Validation failed'}
                            </span>
                          </div>
                          {ex.error_message && (
                            <div style={{ fontSize: '0.8rem', color: '#FCA5A5', marginTop: '2px', marginBottom: '4px' }}>
                              Error: {ex.error_message}
                            </div>
                          )}
                          {ex.routing_decision?.selection_reason && (
                            <div style={{ fontSize: '0.78rem', color: '#8B949E' }}>
                              Router rationale: {ex.routing_decision.selection_reason}
                            </div>
                          )}
                          {ex.is_fallback && (
                            <div style={{ fontSize: '0.78rem', color: '#FDE68A', marginTop: '4px' }}>
                              Fallback triggered: {ex.fallback_reason}
                            </div>
                          )}

                          {/* Multi-Agent Collaborative Review Badge */}
                          {reviewData && (
                            <div
                              style={{
                                marginTop: '8px',
                                padding: '8px 10px',
                                borderRadius: '6px',
                                background: reviewData.action === 'accept'
                                  ? '#0E2318'
                                  : '#261B0E',
                                border: `1px solid ${reviewData.action === 'accept' ? '#1D5A38' : '#6E4919'}`,
                                fontSize: '0.78rem',
                              }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600 }}>
                                <span>Collaborative peer review ({reviewData.reviewer_provider})</span>
                                <span>{reviewData.action}</span>
                              </div>
                              <div style={{ marginTop: '2px', color: '#8B949E' }}>
                                {reviewData.feedback}
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            ) : (
              <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
                Select a task from the left to inspect its details and execution stream.
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── TAB 2: INTERACTIVE VISUAL DAG CANVAS ───────────────────────── */}
      {activeTab === 'dag' && (
        <div style={{ height: '700px', width: '100%', position: 'relative' }}>
          <DagCanvas
            projectId={projectId}
            tasks={tasks}
            onSelectTask={(taskId: string) => {
              setSelectedTaskId(taskId);
              setActiveTab('board');
            }}
            onOpenApproval={(taskId: string) => {
              setApprovalTaskId(taskId);
              setShowApprovalModal(true);
            }}
            onRefresh={() => {
              loadProjectAndTasks();
            }}
          />
        </div>
      )}

      {/* ── TAB 3: AI PLANNER ───────────────────────────────────────────── */}
      {activeTab === 'planner' && (
        <div className="glass-panel" style={{ padding: '32px', maxWidth: '800px', margin: '0 auto', background: '#161B22', border: '1px solid #2A313C' }}>
          <h2 className="font-serif" style={{ fontSize: '1.5rem', color: '#E6EDF3', marginBottom: '8px', fontWeight: 600 }}>
            AI goal decomposition and DAG planning
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '20px', lineHeight: 1.5 }}>
            Describe a high-level feature or project objective. SYNQ&apos;s Planner will automatically break it into a
            topological Directed Acyclic Graph (DAG) with dependency ordering and domain-tailored acceptance criteria.
          </p>

          {planSuccessMsg && (
            <div style={{ padding: '10px 14px', background: '#0E2318', border: '1px solid #1D5A38', color: '#86EFAC', borderRadius: '6px', marginBottom: '16px', fontSize: '0.85rem' }}>
              {planSuccessMsg}
            </div>
          )}

          {planErrorMsg && (
            <div style={{ padding: '10px 14px', background: '#291013', border: '1px solid #66242B', color: '#FCA5A5', borderRadius: '6px', marginBottom: '16px', fontSize: '0.85rem', lineHeight: 1.5 }}>
              {planErrorMsg}
            </div>
          )}

          <form onSubmit={handleRunPlanner} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, color: '#8B949E', marginBottom: '6px' }}>
                Project objective / goal
              </label>
              <textarea
                rows={4}
                required
                placeholder="e.g. Implement full authentication with JWT, bcrypt password hashing, session refresh, and test coverage."
                value={plannerGoal}
                onChange={(e) => setPlannerGoal(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  background: '#0E1116',
                  border: '1px solid #2A313C',
                  borderRadius: '6px',
                  color: '#E6EDF3',
                  fontSize: '0.875rem',
                  resize: 'vertical',
                }}
              />
            </div>

            <button
              type="submit"
              disabled={planning}
              className="btn-primary"
              style={{ alignSelf: 'flex-start', padding: '8px 20px', fontSize: '0.85rem' }}
            >
              {planning ? 'Decomposing goal with AI...' : 'Decompose goal into DAG subtasks'}
            </button>
          </form>
        </div>
      )}

      {/* ── TAB 4: FALKORDB MEMORY GRAPH ────────────────────────────────── */}
      {activeTab === 'memory' && (
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px' }}>
          {/* Visual Graph Canvas / Representation */}
          <div
            className="glass-panel"
            style={{
              padding: '24px',
              minHeight: '520px',
              display: 'flex',
              flexDirection: 'column',
              background: '#161B22',
              border: '1px solid #2A313C',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#8B949E', letterSpacing: '0.02em' }}>
                Continuous memory graph
              </span>
              <span className="badge badge-completed">Live graph</span>
            </div>

            {memoryGraph && memoryGraph.nodes.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', overflowY: 'auto' }}>
                <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '8px' }}>
                  <span style={{ fontSize: '0.75rem', color: '#ff922b' }}>● Project</span>
                  <span style={{ fontSize: '0.75rem', color: '#51cf66' }}>● Task</span>
                  <span style={{ fontSize: '0.75rem', color: '#339af0' }}>● Execution</span>
                  <span style={{ fontSize: '0.75rem', color: '#f08c00' }}>● Artifact</span>
                  <span style={{ fontSize: '0.75rem', color: '#cc5de8' }}>● Decision</span>
                </div>

                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                    gap: '12px',
                  }}
                >
                  {memoryGraph.nodes.map((node) => {
                    const isSelected = selectedGraphNode?.id === node.id;
                    let color = '#51cf66';
                    if (node.label === 'Project') color = '#ff922b';
                    if (node.label === 'Execution') color = '#339af0';
                    if (node.label === 'Artifact') color = '#f08c00';
                    if (node.label === 'Decision') color = '#cc5de8';

                    return (
                      <div
                        key={node.id}
                        onClick={() => setSelectedGraphNode(node)}
                        style={{
                          padding: '12px 14px',
                          background: isSelected ? '#1F242C' : '#0E1116',
                          border: `1px solid ${isSelected ? color : '#2A313C'}`,
                          borderRadius: '6px',
                          cursor: 'pointer',
                          transition: 'border-color 0.15s ease',
                        }}
                      >
                        <div style={{ fontSize: '0.7rem', fontWeight: 600, color }}>
                          {node.label}
                        </div>
                        <div style={{ fontSize: '0.85rem', fontWeight: 500, color: '#E6EDF3', marginTop: '4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {node.name || node.title || node.description || node.id}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div style={{ margin: 'auto', textAlign: 'center', color: '#8B949E', fontSize: '0.875rem' }}>
                No graph nodes committed yet. Run tasks to populate persistent artifacts and execution decisions.
              </div>
            )}
          </div>

          {/* Right Column: Node Inspector */}
          <div className="glass-panel" style={{ padding: '24px', background: '#161B22', border: '1px solid #2A313C' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#8B949E', letterSpacing: '0.02em' }}>
              Memory node inspector
            </span>

            {selectedGraphNode ? (
              <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div>
                  <span className="badge badge-completed">{selectedGraphNode.label}</span>
                  <h3 style={{ fontSize: '1.15rem', color: '#E6EDF3', marginTop: '8px', fontWeight: 600 }}>
                    {selectedGraphNode.name || selectedGraphNode.title || selectedGraphNode.id}
                  </h3>
                </div>

                <div style={{ fontSize: '0.8rem', color: '#8B949E', fontFamily: 'monospace' }}>
                  ID: {selectedGraphNode.id}
                </div>

                {selectedGraphNode.preview && (
                  <div>
                    <div style={{ fontSize: '0.75rem', color: '#8B949E', marginBottom: '4px' }}>
                      Artifact content preview:
                    </div>
                    <div style={{ background: '#0E1116', border: '1px solid #2A313C', padding: '12px', borderRadius: '6px', fontSize: '0.8rem', color: '#E6EDF3', whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>
                      {selectedGraphNode.preview}
                    </div>
                  </div>
                )}

                {selectedGraphNode.rationale && (
                  <div>
                    <div style={{ fontSize: '0.75rem', color: '#8B949E', marginBottom: '4px' }}>
                      Decision rationale:
                    </div>
                    <div style={{ background: '#0E1116', border: '1px solid #2A313C', padding: '12px', borderRadius: '6px', fontSize: '0.8rem', color: '#FDE68A' }}>
                      {selectedGraphNode.rationale}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '60px 0', color: '#8B949E', fontSize: '0.85rem' }}>
                Click any node in the graph to inspect its memory attributes and context lineage.
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Human-in-the-Loop Task Approval Modal ───────────────────────── */}
      {showApprovalModal && approvalTaskId && (
        <TaskApprovalModal
          taskId={approvalTaskId}
          isOpen={showApprovalModal}
          onClose={() => {
            setShowApprovalModal(false);
            setApprovalTaskId(null);
          }}
          onActionComplete={() => {
            loadProjectAndTasks();
            if (selectedTaskId) {
              loadTaskDetail(selectedTaskId);
            }
          }}
        />
      )}

      {/* ── Project Deliverables Export Modal ───────────────────────────── */}
      <ExportModal
        projectId={projectId}
        projectName={project.name}
        isOpen={showExportModal}
        onClose={() => setShowExportModal(false)}
      />

      {/* ── Add Task Modal ──────────────────────────────────────────────── */}
      {showAddTaskModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.65)',
            backdropFilter: 'blur(4px)',
            zIndex: 100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
        >
          <div className="glass-panel" style={{ width: '100%', maxWidth: '500px', padding: '24px', background: '#161B22', border: '1px solid #2A313C', borderRadius: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h2 className="font-serif" style={{ fontSize: '1.25rem', color: '#E6EDF3', margin: 0, fontWeight: 600 }}>Add new task</h2>
              <button
                onClick={() => setShowAddTaskModal(false)}
                style={{ background: 'none', border: 'none', color: '#8B949E', fontSize: '1.25rem', cursor: 'pointer', lineHeight: 1 }}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateTask} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, color: '#8B949E', marginBottom: '4px' }}>
                  Task title *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Implement FalkorDB graph service"
                  value={newTaskTitle}
                  onChange={(e) => setNewTaskTitle(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    background: '#0E1116',
                    border: '1px solid #2A313C',
                    borderRadius: '6px',
                    color: '#E6EDF3',
                    fontSize: '0.85rem',
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, color: '#8B949E', marginBottom: '4px' }}>
                  Task type
                </label>
                <select
                  value={newTaskType}
                  onChange={(e) => setNewTaskType(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    background: '#0E1116',
                    border: '1px solid #2A313C',
                    borderRadius: '6px',
                    color: '#E6EDF3',
                    fontSize: '0.85rem',
                  }}
                >
                  <option value="code">Code (specialized LLM)</option>
                  <option value="research">Research and citations</option>
                  <option value="write">Documentation and writing</option>
                  <option value="analyze">Analysis and planning</option>
                  <option value="general">General objective</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, color: '#8B949E', marginBottom: '4px' }}>
                  Description / prompt
                </label>
                <textarea
                  rows={3}
                  placeholder="Instructions for the assigned AI model..."
                  value={newTaskDesc}
                  onChange={(e) => setNewTaskDesc(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    background: '#0E1116',
                    border: '1px solid #2A313C',
                    borderRadius: '6px',
                    color: '#E6EDF3',
                    fontSize: '0.85rem',
                    resize: 'vertical',
                  }}
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <input
                  type="checkbox"
                  id="approvalCheck"
                  checked={newTaskApproval}
                  onChange={(e) => setNewTaskApproval(e.target.checked)}
                />
                <label htmlFor="approvalCheck" style={{ fontSize: '0.85rem', color: '#8B949E' }}>
                  Require human approval before execution
                </label>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '8px' }}>
                <button type="button" onClick={() => setShowAddTaskModal(false)} className="btn-secondary" style={{ padding: '6px 14px', fontSize: '0.85rem' }}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary" style={{ padding: '6px 14px', fontSize: '0.85rem' }}>
                  Create task
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
