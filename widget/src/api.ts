/**
 * ChatAPI -- WebSocket client with reconnection and REST fallback.
 *
 * Primary transport: WebSocket.
 * Fallback: REST endpoints when WebSocket is unavailable.
 * Session ID is persisted in localStorage across page reloads.
 */

export interface ChatMessage {
  type: "message" | "typing" | "booking";
  text: string;
  data?: Record<string, unknown>;
  timestamp?: string;
  role?: "user" | "assistant";
}

export interface InitResponse {
  session_id: string;
  greeting: string;
}

export interface SendResponse {
  text: string;
  qualification_stage?: string;
}

export interface HistoryMessage {
  role: string;
  content: string;
  message_type: string;
  created_at: string;
}

type MessageCallback = (msg: ChatMessage) => void;
type StatusCallback = (connected: boolean) => void;

const STORAGE_KEY = "ai_widget_session_id";
const MAX_RECONNECT_ATTEMPTS = 10;
const BASE_RECONNECT_DELAY = 1000; // 1s
const MAX_RECONNECT_DELAY = 30000; // 30s

function generateUUID(): string {
  // Simple UUID v4 generator (no crypto dependency for max compat)
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export class ChatAPI {
  private channelId: string;
  private apiUrl: string;
  private ws: WebSocket | null = null;
  private sessionId: string;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private messageCallbacks: MessageCallback[] = [];
  private typingCallbacks: Array<() => void> = [];
  private statusCallbacks: StatusCallback[] = [];
  private intentionalClose = false;

  constructor(channelId: string, apiUrl: string) {
    this.channelId = channelId;
    this.apiUrl = apiUrl.replace(/\/$/, ""); // strip trailing slash

    // Restore or generate session ID
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      this.sessionId = stored;
    } else {
      this.sessionId = generateUUID();
      localStorage.setItem(STORAGE_KEY, this.sessionId);
    }
  }

  /** Get the current session ID. */
  getSessionId(): string {
    return this.sessionId;
  }

  // --------------- WebSocket methods ---------------

  /** Connect to the WebSocket endpoint. */
  async connect(): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      this.intentionalClose = false;

      // Determine ws:// or wss:// from http:// or https://
      const wsProtocol = this.apiUrl.startsWith("https") ? "wss" : "ws";
      const wsBase = this.apiUrl.replace(/^https?/, wsProtocol);
      const wsUrl = `${wsBase}/api/v1/widget/ws?channel_id=${this.channelId}&session_id=${this.sessionId}`;

      try {
        this.ws = new WebSocket(wsUrl);
      } catch {
        // WebSocket constructor can throw in some environments
        this.notifyStatus(false);
        reject(new Error("WebSocket not supported"));
        return;
      }

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.notifyStatus(true);
        resolve();
      };

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const data: ChatMessage = JSON.parse(event.data);
          if (data.type === "typing") {
            this.typingCallbacks.forEach((cb) => cb());
          } else {
            this.messageCallbacks.forEach((cb) => cb(data));
          }
        } catch {
          // Ignore malformed messages
        }
      };

      this.ws.onclose = () => {
        this.notifyStatus(false);
        if (!this.intentionalClose) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = () => {
        this.notifyStatus(false);
        // onclose will fire after onerror, so reconnect is handled there
        if (this.ws?.readyState === WebSocket.CONNECTING) {
          reject(new Error("WebSocket connection failed"));
        }
      };
    });
  }

  /** Disconnect the WebSocket intentionally. */
  disconnect(): void {
    this.intentionalClose = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close(1000, "Client disconnect");
      this.ws = null;
    }
    this.notifyStatus(false);
  }

  /** Send a text message via WebSocket. */
  sendMessage(text: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          type: "message",
          text,
          session_id: this.sessionId,
        })
      );
    } else {
      // Fallback to REST
      this.sendMessageREST(text).catch(() => {
        // Silently fail -- the UI should show an error based on connection status
      });
    }
  }

  /** Register a callback for incoming messages. */
  onMessage(callback: MessageCallback): void {
    this.messageCallbacks.push(callback);
  }

  /** Register a callback for typing indicators. */
  onTyping(callback: () => void): void {
    this.typingCallbacks.push(callback);
  }

  /** Register a callback for connection status changes. */
  onStatusChange(callback: StatusCallback): void {
    this.statusCallbacks.push(callback);
  }

  /** Whether WebSocket is currently connected. */
  get isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  // --------------- REST fallback methods ---------------

  /** Initialize a new chat session via REST. */
  async initSession(): Promise<InitResponse> {
    const res = await fetch(`${this.apiUrl}/api/v1/widget/init`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel_id: this.channelId }),
    });
    if (!res.ok) throw new Error(`Init failed: ${res.status}`);
    const data: InitResponse = await res.json();
    // Update session ID if the server assigned one
    if (data.session_id) {
      this.sessionId = data.session_id;
      localStorage.setItem(STORAGE_KEY, this.sessionId);
    }
    return data;
  }

  /** Send a message via REST (fallback when WebSocket is down). */
  async sendMessageREST(text: string): Promise<SendResponse> {
    const res = await fetch(`${this.apiUrl}/api/v1/widget/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        channel_id: this.channelId,
        session_id: this.sessionId,
        text,
      }),
    });
    if (!res.ok) throw new Error(`Send failed: ${res.status}`);
    return res.json();
  }

  /** Fetch message history via REST. */
  async getHistory(): Promise<HistoryMessage[]> {
    const res = await fetch(
      `${this.apiUrl}/api/v1/widget/history/${this.sessionId}`
    );
    if (!res.ok) throw new Error(`History failed: ${res.status}`);
    const data = await res.json();
    return data.messages || [];
  }

  // --------------- Private helpers ---------------

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      return; // Give up
    }

    const delay = Math.min(
      BASE_RECONNECT_DELAY * Math.pow(2, this.reconnectAttempts),
      MAX_RECONNECT_DELAY
    );
    this.reconnectAttempts++;

    this.reconnectTimer = setTimeout(async () => {
      try {
        await this.connect();
        // On successful reconnect, load missed messages
        const history = await this.getHistory();
        history.forEach((msg) => {
          this.messageCallbacks.forEach((cb) =>
            cb({
              type: "message",
              text: msg.content,
              role: msg.role as "user" | "assistant",
              timestamp: msg.created_at,
            })
          );
        });
      } catch {
        // connect() rejection will trigger onclose -> scheduleReconnect
      }
    }, delay);
  }

  private notifyStatus(connected: boolean): void {
    this.statusCallbacks.forEach((cb) => cb(connected));
  }
}
