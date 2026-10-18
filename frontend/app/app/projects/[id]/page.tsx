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
            <h1 className="font-serif" style={{ fontSize: '1.8rem', color: '#fff', margin: 0 }}>
              {project.name}
            </h1>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: '4px',
                background: 'rgba(255, 255, 255, 0.08)',
                color: 'var(--accent-orange-light)',
              }}
            >
              {project.domain}
            </span>
            <span className={`badge badge-${project.status}`}>{project.status}</span>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', maxWidth: '700px', margin: 0 }}>
            {project.description || 'No description provided.'}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <button
            onClick={() => setShowExportModal(true)}
            className="btn-secondary"
            style={{ padding: '8px 16px', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <span>📦</span> Export Deliverables
          </button>
          <button
            onClick={() => setActiveTab('planner')}
            className="btn-secondary"
            style={{ padding: '8px 16px', fontSize: '0.9rem' }}
          >
            ✦ AI Planner
          </button>
          <button
            onClick={() => setShowAddTaskModal(true)}
            className="btn-primary"
            style={{ padding: '8px 18px', fontSize: '0.9rem' }}
          >
            + Add Task
          </button>
        </div>
      </div>

      {/* ── Tab Switcher ────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: '12px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '12px', flexWrap: 'wrap' }}>
        <button
          onClick={() => setActiveTab('board')}
          style={{
            padding: '8px 18px',
            borderRadius: '6px',
            fontWeight: 600,
            fontSize: '0.95rem',
            background: activeTab === 'board' ? 'var(--accent-orange-subtle)' : 'transparent',
            color: activeTab === 'board' ? 'var(--accent-orange)' : 'var(--text-muted)',
            border: activeTab === 'board' ? '1px solid var(--accent-orange)' : '1px solid transparent',
            cursor: 'pointer',
          }}
        >
          Task Board & Monitor ({tasks.length})
        </button>

        <button
          onClick={() => setActiveTab('dag')}
          style={{
            padding: '8px 18px',
            borderRadius: '6px',
            fontWeight: 600,
            fontSize: '0.95rem',
            background: activeTab === 'dag' ? 'var(--accent-orange-subtle)' : 'transparent',
            color: activeTab === 'dag' ? 'var(--accent-orange)' : 'var(--text-muted)',
            border: activeTab === 'dag' ? '1px solid var(--accent-orange)' : '1px solid transparent',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <span>🗺️</span> Interactive DAG Canvas
        </button>

        <button
          onClick={() => {
            setActiveTab('memory');
            loadMemoryGraph();
          }}
          style={{
            padding: '8px 18px',
            borderRadius: '6px',
            fontWeight: 600,
            fontSize: '0.95rem',
            background: activeTab === 'memory' ? 'var(--accent-orange-subtle)' : 'transparent',
            color: activeTab === 'memory' ? 'var(--accent-orange)' : 'var(--text-muted)',
            border: activeTab === 'memory' ? '1px solid var(--accent-orange)' : '1px solid transparent',
            cursor: 'pointer',
          }}
        >
          FalkorDB Memory Graph ({memoryGraph?.nodes.length || 0} Nodes)
        </button>

        <button
          onClick={() => setActiveTab('planner')}
          style={{
            padding: '8px 18px',
            borderRadius: '6px',
            fontWeight: 600,
            fontSize: '0.95rem',
            background: activeTab === 'planner' ? 'var(--accent-orange-subtle)' : 'transparent',
            color: activeTab === 'planner' ? 'var(--accent-orange)' : 'var(--text-muted)',
            border: activeTab === 'planner' ? '1px solid var(--accent-orange)' : '1px solid transparent',
            cursor: 'pointer',
          }}
        >
          AI Goal Decomposition
        </button>
      </div>

      {/* ── TAB 1: TASK BOARD & MONITOR ─────────────────────────────────── */}
      {activeTab === 'board' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.3fr', gap: '24px', alignItems: 'start' }}>
          {/* Left Column: Task List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {tasks.length === 0 ? (
              <div className="glass-panel" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
                No tasks yet. Use <strong>+ Add Task</strong> or the <strong>AI Planner</strong> to decompose goals.
              </div>
            ) : (
              tasks.map((task, idx) => {
                const isSelected = selectedTaskId === task.id;
                const isExecuting = executingTaskId === task.id;
                const isAwaitingApproval = task.status === 'awaiting_approval';
                const isRejected = task.status === 'rejected';
                const isBlocked = task.status === 'blocked';

                return (
                  <div
                    key={task.id}
                    onClick={() => setSelectedTaskId(task.id)}
                    className="glass-panel"
                    style={{
                      padding: '16px 20px',
                      cursor: 'pointer',
                      borderColor: isSelected
                        ? 'var(--accent-orange)'
                        : isAwaitingApproval
                        ? '#f59e0b'
                        : isRejected
                        ? '#ef4444'
                        : 'var(--border-subtle)',
                      background: isSelected
                        ? 'rgba(240, 140, 0, 0.05)'
                        : isAwaitingApproval
                        ? 'rgba(245, 158, 11, 0.04)'
                        : isRejected
                        ? 'rgba(239, 68, 68, 0.04)'
                        : 'var(--bg-card)',
                      transition: 'all 0.15s ease',
                      borderLeft: isAwaitingApproval
                        ? '4px solid #f59e0b'
                        : isRejected
                        ? '4px solid #ef4444'
                        : isBlocked
                        ? '4px solid #6b7280'
                        : undefined,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)' }}>
                          #{idx + 1}
                        </span>
                        <span
                          style={{
                            fontSize: '0.75rem',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            background: 'rgba(255, 255, 255, 0.06)',
                            color: 'var(--accent-orange-light)',
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

                    <h4 style={{ fontSize: '1rem', color: '#fff', marginBottom: '6px' }}>{task.title}</h4>

                    {isAwaitingApproval && (
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px' }}>
                        <span style={{ fontSize: '0.78rem', color: '#fbbf24' }}>
                          ⚠️ Operator Approval Required
                        </span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setApprovalTaskId(task.id);
                            setShowApprovalModal(true);
                          }}
                          className="btn-primary"
                          style={{
                            padding: '4px 10px',
                            fontSize: '0.75rem',
                            background: '#f59e0b',
                            color: '#000',
                            fontWeight: 700,
                          }}
                        >
                          Review & Approve
                        </button>
                      </div>
                    )}

                    {isRejected && task.rejection_reason && (
                      <div style={{ fontSize: '0.75rem', color: '#fca5a5', marginTop: '6px' }}>
                        Rejection reason: {task.rejection_reason}
                      </div>
                    )}

                    {task.dependencies.length > 0 && (
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                        Depends on: {task.dependencies.length} tasks
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>

          {/* Right Column: Execution Monitor & Detail */}
          <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {selectedTaskDetail ? (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <span
                      style={{
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        color: 'var(--accent-orange)',
                      }}
                    >
                      Task Inspector
                    </span>
                    <h2 style={{ fontSize: '1.35rem', color: '#fff', marginTop: '4px' }}>
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
                        style={{ padding: '6px 14px', fontSize: '0.85rem', background: '#f59e0b', color: '#000', fontWeight: 700 }}
                      >
                        ⚠️ Review & Approve
                      </button>
                    )}

                    {selectedTaskDetail.status === 'rejected' && (
                      <button
                        onClick={() => {
                          setApprovalTaskId(selectedTaskDetail.id);
                          setShowApprovalModal(true);
                        }}
                        className="btn-secondary"
                        style={{ padding: '6px 14px', fontSize: '0.85rem', color: '#fca5a5', borderColor: '#ef4444' }}
                      >
                        ✏️ Edit & Resubmit
                      </button>
                    )}

                    {selectedTaskDetail.status !== 'awaiting_approval' && selectedTaskDetail.status !== 'rejected' && (
                      <button
                        onClick={() => handleExecuteTask(selectedTaskDetail.id)}
                        disabled={executingTaskId === selectedTaskDetail.id || selectedTaskDetail.status === 'blocked'}
                        className="btn-primary"
                        style={{ padding: '6px 16px', fontSize: '0.85rem' }}
                      >
                        {executingTaskId === selectedTaskDetail.id ? 'Running Agent...' : '▶ Run Task'}
                      </button>
                    )}
                  </div>
                </div>

                <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  {selectedTaskDetail.description || 'No specific instructions provided.'}
                </div>

                {selectedTaskDetail.approval_reason && (
                  <div
                    style={{
                      padding: '10px 14px',
                      background: 'rgba(34, 197, 94, 0.08)',
                      borderRadius: '8px',
                      borderLeft: '3px solid #22c55e',
                      fontSize: '0.85rem',
                      color: '#86efac',
                    }}
                  >
                    <strong>Operator Approval:</strong> {selectedTaskDetail.approval_reason} (Approved by: {selectedTaskDetail.approved_by || 'Human Operator'})
                  </div>
                )}

                {selectedTaskDetail.rejection_reason && (
                  <div
                    style={{
                      padding: '10px 14px',
                      background: 'rgba(239, 68, 68, 0.08)',
                      borderRadius: '8px',
                      borderLeft: '3px solid #ef4444',
                      fontSize: '0.85rem',
                      color: '#fca5a5',
                    }}
                  >
                    <strong>Rejection Notice:</strong> {selectedTaskDetail.rejection_reason}
                  </div>
                )}

                {selectedTaskDetail.acceptance_criteria && (
                  <div
                    style={{
                      padding: '10px 14px',
                      background: 'rgba(255, 255, 255, 0.03)',
                      borderRadius: '8px',
                      borderLeft: '3px solid var(--accent-orange)',
                      fontSize: '0.85rem',
                    }}
                  >
                    <strong>Acceptance Criteria:</strong> {selectedTaskDetail.acceptance_criteria}
                  </div>
                )}

                {/* Real-time Streaming Output / Output Box */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                      Agent Output {executingTaskId === selectedTaskDetail.id && '(Live Stream)'}
                    </span>
                    {executingTaskId === selectedTaskDetail.id && (
                      <span style={{ fontSize: '0.8rem', color: 'var(--status-running)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span className="pulse-dot"></span> Streaming Tokens via WebSocket
                      </span>
                    )}
                  </div>

                  <div
                    style={{
                      background: '#0d1014',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: '8px',
                      padding: '16px',
                      minHeight: '180px',
                      maxHeight: '340px',
                      overflowY: 'auto',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.82rem',
                      lineHeight: 1.5,
                      color: '#e6edf3',
                      whiteSpace: 'pre-wrap',
                    }}
                  >
                    {executingTaskId === selectedTaskDetail.id
                      ? liveStreamOutput || 'Waiting for agent generation...'
                      : selectedTaskDetail.executions.length > 0 && selectedTaskDetail.executions[0].output
                      ? selectedTaskDetail.executions[0].output
                      : selectedTaskDetail.executions.length > 0 && selectedTaskDetail.executions[0].error_message
                      ? `Execution failed: ${selectedTaskDetail.executions[0].error_message}`
                      : 'No execution output yet. Click "Run Task" to trigger routing and execution.'}
                  </div>
                </div>

                {/* Routing & Execution History */}
                {selectedTaskDetail.executions.length > 0 && (
                  <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '16px' }}>
                    <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '10px' }}>
                      Routing Decision & Quality Audit
                    </div>
                    {selectedTaskDetail.executions.map((ex) => {
                      const reviewData = ex.validation_result?.collaborative_review;

                      return (
                        <div
                          key={ex.id}
                          style={{
                            padding: '12px 14px',
                            background: 'rgba(255, 255, 255, 0.03)',
                            borderRadius: '8px',
                            marginBottom: '8px',
                            fontSize: '0.85rem',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                            <span>
                              Attempt #{ex.attempt}: <strong>{ex.provider_id}:{ex.model_id}</strong>
                            </span>
                            <span style={{ color: ex.validation_passed ? 'var(--status-completed)' : 'var(--status-failed)' }}>
                              {ex.validation_passed
                                ? 'Validation: Passed ✓'
                                : ex.error_message
                                ? 'Execution Failed ✕'
                                : 'Validation: Failed ✕'}
                            </span>
                          </div>
                          {ex.error_message && (
                            <div style={{ fontSize: '0.8rem', color: 'var(--status-failed)', marginTop: '2px', marginBottom: '4px' }}>
                              Error: {ex.error_message}
                            </div>
                          )}
                          {ex.routing_decision?.selection_reason && (
                            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                              Router rationale: {ex.routing_decision.selection_reason}
                            </div>
                          )}
                          {ex.is_fallback && (
                            <div style={{ fontSize: '0.78rem', color: 'var(--accent-orange-light)', marginTop: '4px' }}>
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
                                  ? 'rgba(34, 197, 94, 0.08)'
                                  : 'rgba(245, 158, 11, 0.08)',
                                border: `1px solid ${reviewData.action === 'accept' ? 'rgba(34, 197, 94, 0.25)' : 'rgba(245, 158, 11, 0.25)'}`,
                                fontSize: '0.78rem',
                              }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600 }}>
                                <span>🤖 Collaborative Peer Review ({reviewData.reviewer_provider})</span>
                                <span style={{ textTransform: 'uppercase' }}>{reviewData.action}</span>
                              </div>
                              <div style={{ marginTop: '2px', color: 'var(--text-secondary)' }}>
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
        <div className="glass-panel" style={{ padding: '36px', maxWidth: '800px', margin: '0 auto' }}>
          <h2 className="font-serif" style={{ fontSize: '1.6rem', color: '#fff', marginBottom: '8px' }}>
            ✦ AI Goal Decomposition & DAG Planning
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', marginBottom: '24px', lineHeight: 1.5 }}>
            Describe a high-level feature or project objective. SYNQ&apos;s Planner will automatically break it into a
            topological Directed Acyclic Graph (DAG) with dependency ordering and domain-tailored acceptance criteria.
          </p>

          {planSuccessMsg && (
            <div style={{ padding: '12px 16px', background: 'rgba(81, 207, 102, 0.15)', color: 'var(--status-completed)', borderRadius: '8px', marginBottom: '20px' }}>
              ✓ {planSuccessMsg}
            </div>
          )}

          {planErrorMsg && (
            <div style={{ padding: '12px 16px', background: 'rgba(235, 87, 87, 0.15)', color: '#ff6b6b', borderRadius: '8px', marginBottom: '20px', fontSize: '0.9rem', lineHeight: 1.5 }}>
              ⚠ {planErrorMsg}
            </div>
          )}

          <form onSubmit={handleRunPlanner} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '8px' }}>
                Project Objective / Goal
              </label>
              <textarea
                rows={4}
                required
                placeholder="e.g. Implement full authentication with JWT, bcrypt password hashing, session refresh, and test coverage."
                value={plannerGoal}
                onChange={(e) => setPlannerGoal(e.target.value)}
                style={{
                  width: '100%',
                  padding: '12px 16px',
                  background: 'var(--bg-secondary)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  color: '#fff',
                  fontSize: '0.95rem',
                  resize: 'vertical',
                }}
              />
            </div>

            <button
              type="submit"
              disabled={planning}
              className="btn-primary"
              style={{ alignSelf: 'flex-start', padding: '12px 28px' }}
            >
              {planning ? 'Decomposing Goal with AI...' : 'Decompose Goal into DAG Subtasks →'}
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
              background: '#0d1014',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                FalkorDB Continuous Memory Graph
              </span>
              <span className="badge badge-completed">Live Graph</span>
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
                          background: isSelected ? 'rgba(255, 255, 255, 0.1)' : 'rgba(255, 255, 255, 0.04)',
                          border: `1px solid ${isSelected ? color : 'var(--border-subtle)'}`,
                          borderRadius: '8px',
                          cursor: 'pointer',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        <div style={{ fontSize: '0.7rem', fontWeight: 700, color, textTransform: 'uppercase' }}>
                          {node.label}
                        </div>
                        <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#fff', marginTop: '4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {node.name || node.title || node.description || node.id}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div style={{ margin: 'auto', textAlign: 'center', color: 'var(--text-muted)' }}>
                No graph nodes committed yet. Run tasks to populate FalkorDB with persistent artifacts and execution decisions.
              </div>
            )}
          </div>

          {/* Right Column: Node Inspector */}
          <div className="glass-panel" style={{ padding: '24px' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Memory Node Inspector
            </span>

            {selectedGraphNode ? (
              <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div>
                  <span className="badge badge-completed">{selectedGraphNode.label}</span>
                  <h3 style={{ fontSize: '1.2rem', color: '#fff', marginTop: '8px' }}>
                    {selectedGraphNode.name || selectedGraphNode.title || selectedGraphNode.id}
                  </h3>
                </div>

                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  ID: {selectedGraphNode.id}
                </div>

                {selectedGraphNode.preview && (
                  <div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                      Artifact Content Preview:
                    </div>
                    <div style={{ background: '#090b0e', padding: '12px', borderRadius: '6px', fontSize: '0.8rem', color: '#a5d8ff', whiteSpace: 'pre-wrap' }}>
                      {selectedGraphNode.preview}
                    </div>
                  </div>
                )}

                {selectedGraphNode.rationale && (
                  <div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                      Decision Rationale:
                    </div>
                    <div style={{ background: '#090b0e', padding: '12px', borderRadius: '6px', fontSize: '0.8rem', color: '#ffd43b' }}>
                      {selectedGraphNode.rationale}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
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
            background: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(8px)',
            zIndex: 100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
        >
          <div className="glass-panel" style={{ width: '100%', maxWidth: '500px', padding: '30px', background: 'var(--bg-secondary)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2 className="font-serif" style={{ fontSize: '1.4rem', color: '#fff', margin: 0 }}>Add New Task</h2>
              <button
                onClick={() => setShowAddTaskModal(false)}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '1.4rem', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateTask} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Task Title *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Implement FalkorDB Graph Service"
                  value={newTaskTitle}
                  onChange={(e) => setNewTaskTitle(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    background: 'var(--bg-primary)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    color: '#fff',
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Task Type
                </label>
                <select
                  value={newTaskType}
                  onChange={(e) => setNewTaskType(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    background: 'var(--bg-primary)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    color: '#fff',
                  }}
                >
                  <option value="code">Code (Specialized LLM)</option>
                  <option value="research">Research & Citations</option>
                  <option value="write">Documentation & Writing</option>
                  <option value="analyze">Analysis & Planning</option>
                  <option value="general">General Objective</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Description / Prompt
                </label>
                <textarea
                  rows={3}
                  placeholder="Instructions for the assigned AI model..."
                  value={newTaskDesc}
                  onChange={(e) => setNewTaskDesc(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    background: 'var(--bg-primary)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    color: '#fff',
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
                <label htmlFor="approvalCheck" style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  Require human approval before execution
                </label>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '10px' }}>
                <button type="button" onClick={() => setShowAddTaskModal(false)} className="btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Create Task
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
