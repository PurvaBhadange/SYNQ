'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Task } from '@/lib/api';

export interface DagNode {
  id: string;
  title: string;
  description?: string | null;
  task_type: string;
  status: string;
  priority: number;
  assigned_provider?: string | null;
  assigned_model?: string | null;
  requires_approval: boolean;
  approval_reason?: string | null;
  rejection_reason?: string | null;
  dependencies: string[];
}

export interface DagEdge {
  id: string;
  source: string;
  target: string;
}

interface DagCanvasProps {
  projectId: string;
  tasks: Task[];
  onSelectTask: (taskId: string) => void;
  onOpenApproval: (taskId: string) => void;
  onRefresh: () => void;
}

// Status color palette & icon config
const STATUS_CONFIG: Record<string, { bg: string; border: string; text: string; glow: string; label: string }> = {
  pending: {
    bg: '#1e222d',
    border: '#475569',
    text: '#94a3b8',
    glow: 'none',
    label: 'PENDING',
  },
  assigned: {
    bg: '#172554',
    border: '#3b82f6',
    text: '#93c5fd',
    glow: '0 0 12px rgba(59, 130, 246, 0.4)',
    label: 'QUEUED',
  },
  running: {
    bg: '#083344',
    border: '#06b6d4',
    text: '#67e8f9',
    glow: '0 0 16px rgba(6, 182, 212, 0.6)',
    label: 'RUNNING',
  },
  validating: {
    bg: '#2e1065',
    border: '#a855f7',
    text: '#d8b4fe',
    glow: '0 0 14px rgba(168, 85, 247, 0.5)',
    label: 'VALIDATING',
  },
  completed: {
    bg: '#052e16',
    border: '#22c55e',
    text: '#86efac',
    glow: '0 0 12px rgba(34, 197, 94, 0.4)',
    label: 'COMPLETED',
  },
  failed: {
    bg: '#450a0a',
    border: '#ef4444',
    text: '#fca5a5',
    glow: '0 0 14px rgba(239, 68, 68, 0.5)',
    label: 'FAILED',
  },
  awaiting_approval: {
    bg: '#451a03',
    border: '#f59e0b',
    text: '#fde68a',
    glow: '0 0 18px rgba(245, 158, 11, 0.6)',
    label: 'APPROVAL REQ',
  },
  rejected: {
    bg: '#2d0607',
    border: '#b91c1c',
    text: '#fca5a5',
    glow: 'none',
    label: 'REJECTED',
  },
  blocked: {
    bg: '#18181b',
    border: '#71717a',
    text: '#a1a1aa',
    glow: 'none',
    label: 'BLOCKED',
  },
};

export default function DagCanvas({
  projectId,
  tasks,
  onSelectTask,
  onOpenApproval,
  onRefresh,
}: DagCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Pan & Zoom transform state
  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 40, y: 40 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Selected & hovered node
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  // Quick dependency modal
  const [showDepModal, setShowDepModal] = useState<boolean>(false);
  const [depSourceId, setDepSourceId] = useState<string>('');
  const [depTargetId, setDepTargetId] = useState<string>('');
  const [depError, setDepError] = useState<string | null>(null);
  const [depLoading, setDepLoading] = useState<boolean>(false);

  // 1. Build Layered Topological Graph Layout
  const { nodePositions, edges } = useMemo(() => {
    if (!tasks || tasks.length === 0) {
      return { nodePositions: new Map<string, { x: number; y: number }>(), edges: [] };
    }

    const taskMap = new Map(tasks.map((t) => [t.id, t]));
    const inDegree = new Map<string, number>();
    const outEdges = new Map<string, string[]>();
    const calculatedEdges: DagEdge[] = [];

    // Initialize degrees
    tasks.forEach((t) => {
      inDegree.set(t.id, 0);
      outEdges.set(t.id, []);
    });

    tasks.forEach((t) => {
      t.dependencies.forEach((depId) => {
        if (taskMap.has(depId)) {
          calculatedEdges.push({
            id: `edge-${depId}->${t.id}`,
            source: depId,
            target: t.id,
          });
          const curr = inDegree.get(t.id) || 0;
          inDegree.set(t.id, curr + 1);
          outEdges.get(depId)?.push(t.id);
        }
      });
    });

    // Compute levels (ranks) using BFS from root nodes
    const levels = new Map<string, number>();
    const queue: string[] = [];

    tasks.forEach((t) => {
      if ((inDegree.get(t.id) || 0) === 0) {
        levels.set(t.id, 0);
        queue.push(t.id);
      }
    });

    while (queue.length > 0) {
      const u = queue.shift()!;
      const uLevel = levels.get(u) || 0;
      const neighbors = outEdges.get(u) || [];
      neighbors.forEach((v) => {
        const existing = levels.get(v) || 0;
        if (uLevel + 1 > existing) {
          levels.set(v, uLevel + 1);
        }
        queue.push(v);
      });
    }

    // Group tasks by level for 2D positioning
    const levelGroups = new Map<number, string[]>();
    tasks.forEach((t) => {
      const lvl = levels.get(t.id) || 0;
      if (!levelGroups.has(lvl)) levelGroups.set(lvl, []);
      levelGroups.get(lvl)!.push(t.id);
    });

    const positions = new Map<string, { x: number; y: number }>();
    const LEVEL_WIDTH = 320;
    const NODE_HEIGHT = 140;

    levelGroups.forEach((taskIdsInLevel, lvl) => {
      taskIdsInLevel.forEach((taskId, rank) => {
        positions.set(taskId, {
          x: lvl * LEVEL_WIDTH + 60,
          y: rank * NODE_HEIGHT + 60,
        });
      });
    });

    return { nodePositions: positions, edges: calculatedEdges };
  }, [tasks]);

  // Mouse pan handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return; // Left click only
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPan({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
    setZoom((prev) => Math.min(Math.max(prev * zoomFactor, 0.4), 2.5));
  };

  const fitToView = () => {
    setZoom(1);
    setPan({ x: 40, y: 40 });
  };

  // Upstream & Downstream highlighting
  const highlightedEdgeIds = useMemo(() => {
    const activeId = hoveredNodeId || selectedNodeId;
    if (!activeId) return new Set<string>();

    const activeSet = new Set<string>();
    edges.forEach((e) => {
      if (e.source === activeId || e.target === activeId) {
        activeSet.add(e.id);
      }
    });
    return activeSet;
  }, [hoveredNodeId, selectedNodeId, edges]);

  // Adding dependency through modal
  const handleAddDependency = async () => {
    if (!depSourceId || !depTargetId) {
      setDepError('Please select both tasks.');
      return;
    }
    setDepLoading(true);
    setDepError(null);
    try {
      const res = await fetch(`http://localhost:8000/api/v1/projects/${projectId}/dependencies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_id: depTargetId,
          depends_on_task_id: depSourceId,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to add dependency');
      }
      setShowDepModal(false);
      onRefresh();
    } catch (err: any) {
      setDepError(err.message || 'Error adding dependency');
    } finally {
      setDepLoading(false);
    }
  };

  return (
    <div
      ref={containerRef}
      style={{
        position: 'relative',
        width: '100%',
        height: '620px',
        backgroundColor: '#0a0c10',
        borderRadius: '12px',
        overflow: 'hidden',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        userSelect: 'none',
        cursor: isDragging ? 'grabbing' : 'grab',
      }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onWheel={handleWheel}
    >
      {/* Background Grid */}
      <svg
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
        }}
      >
        <defs>
          <pattern id="dag-grid" width="30" height="30" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r="1" fill="rgba(255, 255, 255, 0.08)" />
          </pattern>
          <marker
            id="dag-arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#64748b" />
          </marker>
          <marker
            id="dag-arrow-active"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#38bdf8" />
          </marker>
        </defs>
        <rect width="100%" height="100%" fill="url(#dag-grid)" />
      </svg>

      {/* Floating Toolbar Controls */}
      <div
        style={{
          position: 'absolute',
          top: '1rem',
          right: '1rem',
          zIndex: 10,
          display: 'flex',
          gap: '0.5rem',
          backgroundColor: 'rgba(18, 20, 26, 0.85)',
          backdropFilter: 'blur(8px)',
          padding: '0.4rem',
          borderRadius: '8px',
          border: '1px solid rgba(255, 255, 255, 0.1)',
        }}
      >
        <button
          type="button"
          onClick={() => setZoom((z) => Math.min(z * 1.2, 2.5))}
          title="Zoom In"
          style={{
            background: 'transparent',
            border: 'none',
            color: '#e2e8f0',
            padding: '0.3rem 0.6rem',
            cursor: 'pointer',
            fontWeight: 700,
            fontSize: '1rem',
          }}
        >
          +
        </button>
        <button
          type="button"
          onClick={() => setZoom((z) => Math.max(z * 0.8, 0.4))}
          title="Zoom Out"
          style={{
            background: 'transparent',
            border: 'none',
            color: '#e2e8f0',
            padding: '0.3rem 0.6rem',
            cursor: 'pointer',
            fontWeight: 700,
            fontSize: '1rem',
          }}
        >
          -
        </button>
        <button
          type="button"
          onClick={fitToView}
          title="Fit to View"
          style={{
            background: 'transparent',
            border: 'none',
            color: '#94a3b8',
            padding: '0.3rem 0.6rem',
            cursor: 'pointer',
            fontSize: '0.8rem',
            fontWeight: 600,
          }}
        >
          Fit View
        </button>
        <button
          type="button"
          onClick={() => {
            setDepError(null);
            setShowDepModal(true);
          }}
          title="Add Dependency Edge"
          style={{
            backgroundColor: 'rgba(59, 130, 246, 0.2)',
            border: '1px solid rgba(59, 130, 246, 0.5)',
            color: '#60a5fa',
            padding: '0.3rem 0.8rem',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '0.8rem',
            fontWeight: 600,
          }}
        >
          + Add Dependency
        </button>
      </div>

      {/* Legend */}
      <div
        style={{
          position: 'absolute',
          bottom: '1rem',
          left: '1rem',
          zIndex: 10,
          display: 'flex',
          gap: '0.75rem',
          flexWrap: 'wrap',
          backgroundColor: 'rgba(18, 20, 26, 0.85)',
          backdropFilter: 'blur(8px)',
          padding: '0.5rem 0.8rem',
          borderRadius: '8px',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          fontSize: '0.75rem',
          color: '#94a3b8',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#22c55e' }} /> Completed
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#06b6d4' }} /> Running
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#f59e0b' }} /> Awaiting Approval
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#ef4444' }} /> Failed/Rejected
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#71717a' }} /> Blocked
        </div>
      </div>

      {/* Main Pan/Zoom World Container */}
      <div
        style={{
          position: 'absolute',
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
          transformOrigin: '0 0',
          transition: isDragging ? 'none' : 'transform 0.15s ease-out',
        }}
      >
        {/* SVG Bezier Edges */}
        <svg
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '3000px',
            height: '2000px',
            overflow: 'visible',
            pointerEvents: 'none',
          }}
        >
          {edges.map((edge) => {
            const p1 = nodePositions.get(edge.source);
            const p2 = nodePositions.get(edge.target);
            if (!p1 || !p2) return null;

            // Connect from right of source to left of target
            const startX = p1.x + 220;
            const startY = p1.y + 40;
            const endX = p2.x;
            const endY = p2.y + 40;

            const dx = Math.abs(endX - startX) * 0.5;
            const pathData = `M ${startX} ${startY} C ${startX + dx} ${startY}, ${endX - dx} ${endY}, ${endX} ${endY}`;
            const isHighlighted = highlightedEdgeIds.has(edge.id);

            return (
              <path
                key={edge.id}
                d={pathData}
                fill="none"
                stroke={isHighlighted ? '#38bdf8' : 'rgba(100, 116, 139, 0.4)'}
                strokeWidth={isHighlighted ? 3 : 1.8}
                strokeDasharray={isHighlighted ? 'none' : 'none'}
                markerEnd={isHighlighted ? 'url(#dag-arrow-active)' : 'url(#dag-arrow)'}
                style={{
                  transition: 'stroke 0.2s, stroke-width 0.2s',
                  filter: isHighlighted ? 'drop-shadow(0 0 6px rgba(56, 189, 248, 0.6))' : 'none',
                }}
              />
            );
          })}
        </svg>

        {/* Task Nodes */}
        {tasks.map((task) => {
          const pos = nodePositions.get(task.id) || { x: 60, y: 60 };
          const statusKey = task.status in STATUS_CONFIG ? task.status : 'pending';
          const cfg = STATUS_CONFIG[statusKey];
          const isSelected = selectedNodeId === task.id;
          const isHovered = hoveredNodeId === task.id;

          return (
            <div
              key={task.id}
              onClick={(e) => {
                e.stopPropagation();
                setSelectedNodeId(task.id);
                onSelectTask(task.id);
              }}
              onMouseEnter={() => setHoveredNodeId(task.id)}
              onMouseLeave={() => setHoveredNodeId(null)}
              style={{
                position: 'absolute',
                left: `${pos.x}px`,
                top: `${pos.y}px`,
                width: '220px',
                padding: '0.85rem',
                borderRadius: '8px',
                backgroundColor: cfg.bg,
                border: `1.5px solid ${isSelected ? '#38bdf8' : cfg.border}`,
                boxShadow: isSelected
                  ? '0 0 20px rgba(56, 189, 248, 0.6)'
                  : isHovered
                  ? cfg.glow
                  : '0 4px 10px rgba(0, 0, 0, 0.5)',
                color: '#f8fafc',
                cursor: 'pointer',
                transition: 'transform 0.15s, box-shadow 0.15s, border-color 0.15s',
                transform: isHovered ? 'scale(1.03)' : 'scale(1)',
                zIndex: isSelected ? 5 : isHovered ? 4 : 1,
              }}
            >
              {/* Header Badge */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '0.4rem',
                }}
              >
                <span
                  style={{
                    fontSize: '0.65rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    color: cfg.text,
                    letterSpacing: '0.05em',
                  }}
                >
                  {cfg.label}
                </span>
                <span
                  style={{
                    fontSize: '0.7rem',
                    color: '#94a3b8',
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    padding: '0.1rem 0.35rem',
                    borderRadius: '4px',
                  }}
                >
                  P{task.priority}
                </span>
              </div>

              {/* Title */}
              <div
                style={{
                  fontSize: '0.88rem',
                  fontWeight: 600,
                  lineHeight: 1.3,
                  marginBottom: '0.4rem',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
                title={task.title}
              >
                {task.title}
              </div>

              {/* Provider & Action */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontSize: '0.75rem',
                  color: '#94a3b8',
                }}
              >
                <span>{task.assigned_provider || task.task_type}</span>
                {task.status === 'awaiting_approval' && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onOpenApproval(task.id);
                    }}
                    style={{
                      backgroundColor: '#f59e0b',
                      color: '#000',
                      border: 'none',
                      borderRadius: '4px',
                      padding: '0.2rem 0.5rem',
                      fontWeight: 700,
                      fontSize: '0.7rem',
                      cursor: 'pointer',
                    }}
                  >
                    Review
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Add Dependency Modal */}
      {showDepModal && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(4px)',
            zIndex: 100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          onClick={() => setShowDepModal(false)}
        >
          <div
            style={{
              backgroundColor: '#12141a',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '10px',
              padding: '1.5rem',
              width: '420px',
              color: '#f8fafc',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ margin: '0 0 1rem 0', fontSize: '1.1rem' }}>Add Task Dependency Edge</h3>

            {depError && (
              <div style={{ marginBottom: '1rem', padding: '0.6rem', backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#fca5a5', borderRadius: '6px', fontSize: '0.85rem' }}>
                {depError}
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div>
                <label style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'block', marginBottom: '0.3rem' }}>
                  Prerequisite Task (Must Complete First)
                </label>
                <select
                  value={depSourceId}
                  onChange={(e) => setDepSourceId(e.target.value)}
                  style={{
                    width: '100%',
                    backgroundColor: '#1a1d24',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: '6px',
                    padding: '0.5rem',
                    color: '#f8fafc',
                  }}
                >
                  <option value="">Select Prerequisite Task...</option>
                  {tasks.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.title}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'block', marginBottom: '0.3rem' }}>
                  Dependent Task (Waits for Prerequisite)
                </label>
                <select
                  value={depTargetId}
                  onChange={(e) => setDepTargetId(e.target.value)}
                  style={{
                    width: '100%',
                    backgroundColor: '#1a1d24',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: '6px',
                    padding: '0.5rem',
                    color: '#f8fafc',
                  }}
                >
                  <option value="">Select Dependent Task...</option>
                  {tasks.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.title}
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1rem' }}>
                <button
                  type="button"
                  onClick={() => setShowDepModal(false)}
                  style={{
                    backgroundColor: 'transparent',
                    border: '1px solid rgba(255, 255, 255, 0.2)',
                    color: '#94a3b8',
                    padding: '0.5rem 1rem',
                    borderRadius: '6px',
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleAddDependency}
                  disabled={depLoading || !depSourceId || !depTargetId}
                  style={{
                    backgroundColor: '#3b82f6',
                    border: 'none',
                    color: '#fff',
                    fontWeight: 600,
                    padding: '0.5rem 1rem',
                    borderRadius: '6px',
                    cursor: depLoading ? 'not-allowed' : 'pointer',
                  }}
                >
                  {depLoading ? 'Validating...' : 'Confirm Dependency'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
