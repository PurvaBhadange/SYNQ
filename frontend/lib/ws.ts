/**
 * SYNQ WebSocket Client
 * Real-time event subscription for task execution, token streaming, and provider updates.
 */

export interface WebSocketEvent {
  project_id: string;
  event_type:
    | 'connected'
    | 'pong'
    | 'task_started'
    | 'task_token'
    | 'agent_assigned'
    | 'task_completed'
    | 'task_failed'
    | 'task_awaiting_approval'
    | 'task_approved'
    | 'task_rejected'
    | 'task_review_started'
    | 'task_review_completed'
    | 'dependency_added'
    | 'dependency_removed'
    | (string & {});
  timestamp: number;
  data: any;
}

export type EventHandler = (event: WebSocketEvent) => void;

export function getWsBase(): string {
  if (process.env.NEXT_PUBLIC_WS_URL) {
    return process.env.NEXT_PUBLIC_WS_URL.replace(/\/+$/, '');
  }
  if (typeof window !== 'undefined') {
    if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
      // In deployed cloud environment, connect to live Render backend WebSocket
      return 'wss://synq-6p9m.onrender.com/api/v1/ws';
    }
  }
  return 'ws://localhost:8000/api/v1/ws';
}

export class SynqWebSocket {
  private ws: WebSocket | null = null;
  private projectId: string;
  private url: string;
  private handlers: Set<EventHandler> = new Set();
  private reconnectTimer: any = null;
  private isDestroyed = false;

  constructor(projectId: string) {
    this.projectId = projectId;
    const wsBase = getWsBase();
    this.url = `${wsBase}/${projectId}`;
    this.connect();
  }

  private connect() {
    if (this.isDestroyed) return;
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        // Connected
      };

      this.ws.onmessage = (event) => {
        try {
          const parsed: WebSocketEvent = JSON.parse(event.data);
          this.handlers.forEach((h) => h(parsed));
        } catch (err) {
          console.debug('Failed to parse WebSocket event:', err);
        }
      };

      this.ws.onclose = () => {
        if (!this.isDestroyed) {
          this.reconnectTimer = setTimeout(() => this.connect(), 3000);
        }
      };

      this.ws.onerror = (err) => {
        console.debug('WebSocket error:', err);
      };
    } catch (err) {
      if (!this.isDestroyed) {
        this.reconnectTimer = setTimeout(() => this.connect(), 3000);
      }
    }
  }

  public subscribe(handler: EventHandler): () => void {
    this.handlers.add(handler);
    return () => {
      this.handlers.delete(handler);
    };
  }

  public destroy() {
    this.isDestroyed = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.handlers.clear();
  }
}
