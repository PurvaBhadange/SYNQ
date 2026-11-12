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

export function normalizeWsUrl(rawUrl?: string): string {
  if (!rawUrl) return '';
  let cleaned = rawUrl.trim().replace(/[\r\n\t]+/g, '').replace(/\/+$/, '');
  if (!cleaned) return '';
  if (cleaned.startsWith('https://')) {
    cleaned = cleaned.replace(/^https:\/\//, 'wss://');
  } else if (cleaned.startsWith('http://')) {
    cleaned = cleaned.replace(/^http:\/\//, 'ws://');
  } else if (!cleaned.startsWith('ws://') && !cleaned.startsWith('wss://')) {
    cleaned = `wss://${cleaned}`;
  }
  if (cleaned.endsWith('/api/v1/ws')) {
    return cleaned;
  }
  if (cleaned.endsWith('/api/v1')) {
    return `${cleaned}/ws`;
  }
  if (cleaned.endsWith('/ws')) {
    return cleaned;
  }
  return `${cleaned}/api/v1/ws`;
}

export function getWsBase(): string {
  if (process.env.NEXT_PUBLIC_WS_URL) {
    const normalized = normalizeWsUrl(process.env.NEXT_PUBLIC_WS_URL);
    if (normalized) return normalized;
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
  private handlers: Set<EventHandler> = new Set();
  private reconnectTimer: any = null;
  private pingInterval: any = null;
  private isDestroyed = false;
  private reconnectAttempts = 0;

  constructor(projectId: string) {
    this.projectId = projectId;
    this.connect();
  }

  private getFullUrl(): string {
    const wsBase = getWsBase();
    let token = '';
    if (typeof window !== 'undefined') {
      token = localStorage.getItem('synq_token') || sessionStorage.getItem('synq_token') || '';
    }
    const tokenQuery = token ? `?token=${encodeURIComponent(token)}` : '';
    return `${wsBase}/${this.projectId}${tokenQuery}`;
  }

  private connect() {
    if (this.isDestroyed) return;
    try {
      const url = this.getFullUrl();
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        // Start 20-second heartbeat ping to prevent cloud proxy disconnects
        if (this.pingInterval) clearInterval(this.pingInterval);
        this.pingInterval = setInterval(() => {
          if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            try {
              this.ws.send(JSON.stringify({ type: 'ping' }));
            } catch {
              // Ignore ping errors
            }
          }
        }, 20000);
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
        if (this.pingInterval) clearInterval(this.pingInterval);
        if (!this.isDestroyed) {
          // Exponential reconnect backoff: 1s, 2s, 3s, max 5s
          this.reconnectAttempts = Math.min(this.reconnectAttempts + 1, 5);
          const delay = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts), 5000);
          this.reconnectTimer = setTimeout(() => this.connect(), delay);
        }
      };

      this.ws.onerror = (err) => {
        console.debug('WebSocket error:', err);
      };
    } catch (err) {
      if (!this.isDestroyed) {
        this.reconnectTimer = setTimeout(() => this.connect(), 2000);
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
    if (this.pingInterval) clearInterval(this.pingInterval);
    if (this.ws) {
      try {
        this.ws.close();
      } catch {
        // Ignore close errors
      }
      this.ws = null;
    }
    this.handlers.clear();
  }
}
