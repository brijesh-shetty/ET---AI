import type { FeedItem } from './types';

export interface WsConnection {
  disconnect: () => void;
  readonly readyState: () => number | null;
}

const MAX_BACKOFF_MS = 16_000;

function wsUrl(path: string): string {
  if (typeof window === 'undefined') return path;
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  return `${proto}//${host}${path}`;
}

export function connectFeedWebSocket(onItem: (item: FeedItem) => void): WsConnection {
  let ws: WebSocket | null = null;
  let closed = false;
  let backoff = 1000;
  let reconnectHandle: number | null = null;

  function clearReconnect() {
    if (reconnectHandle !== null) {
      window.clearTimeout(reconnectHandle);
      reconnectHandle = null;
    }
  }

  function open() {
    if (closed) return;
    try {
      ws = new WebSocket(wsUrl('/ws/feed'));
    } catch {
      scheduleReconnect();
      return;
    }
    ws.onopen = () => {
      backoff = 1000;
    };
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as FeedItem;
        onItem(data);
      } catch {
        // ignore non-JSON frames
      }
    };
    ws.onerror = () => {
      try {
        ws?.close();
      } catch {
        // ignore
      }
    };
    ws.onclose = () => {
      if (!closed) scheduleReconnect();
    };
  }

  function scheduleReconnect() {
    clearReconnect();
    if (closed) return;
    reconnectHandle = window.setTimeout(() => {
      backoff = Math.min(backoff * 2, MAX_BACKOFF_MS);
      open();
    }, backoff);
  }

  open();

  return {
    disconnect: () => {
      closed = true;
      clearReconnect();
      try {
        ws?.close();
      } catch {
        // ignore
      }
      ws = null;
    },
    readyState: () => ws?.readyState ?? null,
  };
}
