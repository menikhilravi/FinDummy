"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { WSEvent } from "@/types";

type Status = "connecting" | "connected" | "disconnected" | "error";

interface UseWebSocketOptions {
  onMessage?: (event: WSEvent) => void;
  reconnectDelay?: number;
  maxReconnects?: number;
}

export function useWebSocket({
  onMessage,
  reconnectDelay = 3000,
  maxReconnects = 10,
}: UseWebSocketOptions = {}) {
  const [status, setStatus] = useState<Status>("disconnected");
  const [maxRetriesReached, setMaxRetriesReached] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCount = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const connect = useCallback(() => {
    const configured = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";
    // Auto-upgrade to wss:// if page is served over https
    const url = typeof window !== "undefined" && window.location.protocol === "https:"
      ? configured.replace(/^ws:\/\//, "wss://")
      : configured;

    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setStatus("connecting");
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("connected");
      reconnectCount.current = 0;
      setMaxRetriesReached(false);
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as WSEvent;
        onMessageRef.current?.(data);
      } catch {
        // ignore malformed frames
      }
    };

    ws.onerror = () => {
      setStatus("error");
    };

    ws.onclose = () => {
      setStatus("disconnected");
      wsRef.current = null;

      if (reconnectCount.current < maxReconnects) {
        const delay =
          reconnectDelay * Math.pow(1.5, reconnectCount.current);
        reconnectCount.current += 1;
        reconnectTimer.current = setTimeout(connect, delay);
      } else {
        setMaxRetriesReached(true);
      }
    };
  }, [reconnectDelay, maxReconnects]);

  const reconnect = useCallback(() => {
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    wsRef.current?.close();
    reconnectCount.current = 0;
    setMaxRetriesReached(false);
    connect();
  }, [connect]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { status, reconnect, maxRetriesReached };
}
