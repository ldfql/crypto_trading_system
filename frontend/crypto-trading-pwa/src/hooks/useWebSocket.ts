import { useEffect, useRef, useState } from 'react';

export const useWebSocket = (url: string) => {
  const [ws, setWs] = useState<WebSocket | null>(null);
  const reconnectTimeout = useRef<NodeJS.Timeout>();

  useEffect(() => {
    const connect = () => {
      const websocket = new WebSocket(url);

      websocket.onopen = () => {
        console.log('WebSocket connected');
        setWs(websocket);
        if (reconnectTimeout.current) {
          clearTimeout(reconnectTimeout.current);
        }
      };

      websocket.onclose = () => {
        console.log('WebSocket disconnected');
        setWs(null);
        // Attempt to reconnect after 5 seconds
        reconnectTimeout.current = setTimeout(connect, 5000);
      };

      websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    };

    connect();

    return () => {
      if (ws) {
        ws.close();
      }
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
    };
  }, [url]);

  return ws;
};
