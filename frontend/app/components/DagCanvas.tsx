'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Task, tasksApi } from '@/lib/api';

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
    bg: '#12151B',
    border: '#2A313C',
    text: '#8B949E',
    glow: 'none',
    label: 'Pending',
  },
  assigned: {
    bg: '#131B2E',
    border: '#294372',
    text: '#93C5FD',
    glow: 'none',
    label: 'Queued',
  },
  running: {
    bg: '#0C2434',
    border: '#195679',
    text: '#67E8F9',
    glow: 'none',
    label: 'Running',
  },
  validating: {
    bg: '#1E1533',
    border: '#482E78',
    text: '#D8B4FE',
    glow: 'none',
    label: 'Validating',
  },
  completed: {
    bg: '#0E2318',
    border: '#1D5A38',
    text: '#86EFAC',
    glow: 'none',
    label: 'Completed',
  },
  failed: {
    bg: '#291013',
    border: '#66242B',
    text: '#FCA5A5',
    glow: 'none',
    label: 'Failed',
  },
  awaiting_approval: {
    bg: '#261B0E',
    border: '#6E4919',
    text: '#FDE68A',
    glow: 'none',
    label: 'Approval required',
  },
  rejected: {
    bg: '#231215',
    border: '#542026',
    text: '#FCA5A5',
    glow: 'none',
    label: 'Rejected',
  },
  blocked: {
    bg: '#16191F',
    border: '#2B313A',
    text: '#8B949E',
    glow: 'none',
    label: 'Blocked',
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
      await tasksApi.addDependency(projectId, depTargetId, depSourceId);
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
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#f5b841" />
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
          backgroundColor: '#161B22',
          padding: '0.25rem 0.5rem',
          borderRadius: '8px',
          border: '1px solid #2A313C',
        }}
      >
        <button
          type="button"
          onClick={() => setZoom((z) => Math.min(z * 1.2, 2.5))}
          title="Zoom In"
          style={{
            background: 'transparent',
            border: 'none',
            color: '#E6EDF3',
            padding: '0.25rem 0.5rem',
            cursor: 'pointer',
            fontWeight: 600,
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
            color: '#E6EDF3',
            padding: '0.25rem 0.5rem',
            cursor: 'pointer',
            fontWeight: 600,
            fontSize: '1rem',
          }}
        >
          -
        </button>
        <button
          type="button"
          onClick={fitToView}
          title="Fit to view"
          style={{
            background: 'transparent',
            border: 'none',
            color: '#8B949E',
            padding: '0.25rem 0.5rem',
            cursor: 'pointer',
            fontSize: '0.8rem',
            fontWeight: 500,
          }}
        >
          Fit view
        </button>
        <button
          type="button"
          onClick={() => {
            setDepError(null);
            setShowDepModal(true);
          }}
          title="Add dependency edge"
          style={{
            backgroundColor: '#1F242C',
            border: '1px solid #2A313C',
            color: '#E6EDF3',
            padding: '0.25rem 0.75rem',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '0.8rem',
            fontWeight: 500,
          }}
        >
          + Add dependency
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
          backgroundColor: '#161B22',
          padding: '0.5rem 0.75rem',
          borderRadius: '8px',
          border: '1px solid #2A313C',
          fontSize: '0.75rem',
          color: '#8B949E',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#22c55e' }} /> Completed
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#06b6d4' }} /> Running
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#f5b841' }} /> Approval required
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#ef4444' }} /> Failed / rejected
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#8B949E' }} /> Blocked
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
                stroke={isHighlighted ? '#f5b841' : '#2A313C'}
                strokeWidth={isHighlighted ? 2 : 1.5}
                strokeDasharray="none"
                markerEnd={isHighlighted ? 'url(#dag-arrow-active)' : 'url(#dag-arrow)'}
                style={{
                  transition: 'stroke 0.15s, stroke-width 0.15s',
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
                padding: '0.75rem',
                borderRadius: '8px',
                backgroundColor: cfg.bg,
                border: `1px solid ${isSelected ? '#f5b841' : cfg.border}`,
                boxShadow: isSelected
                  ? '0 0 0 1px #f5b841, 0 4px 12px rgba(0, 0, 0, 0.4)'
                  : isHovered
                  ? '0 4px 12px rgba(0, 0, 0, 0.35)'
                  : '0 2px 6px rgba(0, 0, 0, 0.25)',
                color: '#E6EDF3',
                cursor: 'pointer',
                transition: 'transform 0.15s, box-shadow 0.15s, border-color 0.15s',
                transform: isHovered ? 'translateY(-1px)' : 'none',
                zIndex: isSelected ? 5 : isHovered ? 4 : 1,
              }}
            >
              {/* Header Badge */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '0.35rem',
                }}
              >
                <span
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    color: cfg.text,
                    letterSpacing: '0.01em',
                  }}
                >
                  {cfg.label}
                </span>
                <span
                  style={{
                    fontSize: '0.7rem',
                    color: '#8B949E',
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    padding: '0.1rem 0.35rem',
                    borderRadius: '4px',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  P{task.priority}
                </span>
              </div>

              {/* Title */}
              <div
                style={{
                  fontSize: '0.875rem',
                  fontWeight: 500,
                  lineHeight: 1.3,
                  marginBottom: '0.35rem',
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
                  color: '#8B949E',
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
                      backgroundColor: '#f5b841',
                      color: '#0E1116',
                      border: 'none',
                      borderRadius: '4px',
                      padding: '0.2rem 0.5rem',
                      fontWeight: 600,
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
            backgroundColor: 'rgba(0, 0, 0, 0.65)',
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
              backgroundColor: '#161B22',
              border: '1px solid #2A313C',
              borderRadius: '8px',
              padding: '1.25rem',
              width: '420px',
              color: '#E6EDF3',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ margin: '0 0 1rem 0', fontSize: '1rem', fontWeight: 600 }}>Add task dependency edge</h3>

            {depError && (
              <div style={{ marginBottom: '1rem', padding: '0.5rem 0.75rem', backgroundColor: '#291013', border: '1px solid #66242B', color: '#FCA5A5', borderRadius: '6px', fontSize: '0.85rem' }}>
                {depError}
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div>
                <label style={{ fontSize: '0.8rem', color: '#8B949E', display: 'block', marginBottom: '0.25rem' }}>
                  Prerequisite task (must complete first)
                </label>
                <select
                  value={depSourceId}
                  onChange={(e) => setDepSourceId(e.target.value)}
                  style={{
                    width: '100%',
                    backgroundColor: '#0E1116',
                    border: '1px solid #2A313C',
                    borderRadius: '6px',
                    padding: '0.5rem',
                    color: '#E6EDF3',
                    fontSize: '0.85rem',
                  }}
                >
                  <option value="">Select prerequisite task...</option>
                  {tasks.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.title}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ fontSize: '0.8rem', color: '#8B949E', display: 'block', marginBottom: '0.25rem' }}>
                  Dependent task (waits for prerequisite)
                </label>
                <select
                  value={depTargetId}
                  onChange={(e) => setDepTargetId(e.target.value)}
                  style={{
                    width: '100%',
                    backgroundColor: '#0E1116',
                    border: '1px solid #2A313C',
                    borderRadius: '6px',
                    padding: '0.5rem',
                    color: '#E6EDF3',
                    fontSize: '0.85rem',
                  }}
                >
                  <option value="">Select dependent task...</option>
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
                    border: '1px solid #2A313C',
                    color: '#8B949E',
                    padding: '0.4rem 0.8rem',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '0.85rem',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleAddDependency}
                  disabled={depLoading || !depSourceId || !depTargetId}
                  style={{
                    backgroundColor: '#f5b841',
                    border: 'none',
                    color: '#0E1116',
                    fontWeight: 600,
                    padding: '0.4rem 0.8rem',
                    borderRadius: '6px',
                    fontSize: '0.85rem',
                    cursor: depLoading || !depSourceId || !depTargetId ? 'not-allowed' : 'pointer',
                    opacity: depLoading || !depSourceId || !depTargetId ? 0.6 : 1,
                  }}
                >
                  {depLoading ? 'Validating...' : 'Confirm dependency'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
