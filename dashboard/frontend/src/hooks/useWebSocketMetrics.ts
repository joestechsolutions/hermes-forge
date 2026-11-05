import { useEffect, useState } from 'react';
import { SystemMetrics } from '../api';

// Polls the REST metrics endpoint when WebSocket is unavailable (HTTPS tunnels block ws://
// and quick-tunnel wss:// passthrough is unreliable). Tries ws first, falls back to REST.
export function useWebSocketMetrics(url: string) {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [connected, setConnected] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let cancelled = false;
    let pollTimer: ReturnType<typeof setInterval> | null = null;

    const startPolling = () => {
      if (pollTimer || cancelled) return;
      const restUrl = '/api/v1/system/metrics';
      const tick = async () => {
        try {
          const r = await fetch(restUrl);
          if (r.ok && !cancelled) {
            setMetrics(await r.json());
            setUpdatedAt(new Date());
            setConnected(true);
          } else if (!cancelled) {
            setConnected(false);
          }
        } catch {
          /* a failed update is not a live feed */
          if (!cancelled) setConnected(false);
        }
      };
      tick();
      pollTimer = setInterval(tick, 3000);
    };

    try {
      ws = new WebSocket(url);
      ws.onopen = () => setConnected(false); // OPEN is not proof that a data frame arrived.
      ws.onmessage = (event) => {
        try {
          setMetrics(JSON.parse(event.data));
          setUpdatedAt(new Date());
          setConnected(true);
        } catch (e) {
          console.error('Failed to parse metrics', e);
        }
      };
      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) startPolling();
      };
      ws.onerror = () => {
        setConnected(false);
        if (!cancelled) startPolling();
      };
    } catch (e) {
      console.warn('WebSocket unavailable, falling back to polling:', e);
      startPolling();
    }

    return () => {
      cancelled = true;
      if (pollTimer) clearInterval(pollTimer);
      ws?.close();
    };
  }, [url]);

  return { metrics, connected, updatedAt };
}