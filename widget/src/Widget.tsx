/**
 * Widget.tsx -- Main chat widget UI component.
 *
 * Features:
 *  - Chat bubble button (toggle open/close)
 *  - Message list with user/assistant bubbles
 *  - Text input with Enter / button send
 *  - Typing indicator (three animated dots)
 *  - Connection status indicator
 *  - Auto-scroll to latest message
 *  - Adaptive design (desktop + mobile)
 */

import { useCallback, useEffect, useRef, useState } from "preact/hooks";
import type { ChatMessage, ChatAPI } from "./api";

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  timestamp: string;
}

interface WidgetProps {
  api: ChatAPI;
}

let messageCounter = 0;
function nextId(): string {
  return `msg-${++messageCounter}-${Date.now()}`;
}

export function Widget({ api }: WidgetProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [initialized, setInitialized] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  // Focus input when chat opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // Set up API callbacks (once)
  useEffect(() => {
    api.onMessage((msg: ChatMessage) => {
      if (msg.type === "message" && msg.text) {
        setMessages((prev) => [
          ...prev,
          {
            id: nextId(),
            role: msg.role || "assistant",
            text: msg.text,
            timestamp: msg.timestamp || new Date().toISOString(),
          },
        ]);
        setIsTyping(false);
      }
    });

    api.onTyping(() => {
      setIsTyping(true);
    });

    api.onStatusChange((connected: boolean) => {
      setIsConnected(connected);
    });
  }, [api]);

  // Connect when chat is opened for the first time
  const handleOpen = useCallback(async () => {
    setIsOpen(true);

    // Notify parent (embed.js) about state
    if (window.parent !== window) {
      window.parent.postMessage({ type: "widget:maximize" }, "*");
    }

    if (!initialized) {
      setInitialized(true);
      try {
        // Try WebSocket first
        await api.connect();
      } catch {
        // Fall back to REST init
        try {
          const init = await api.initSession();
          if (init.greeting) {
            setMessages((prev) => [
              ...prev,
              {
                id: nextId(),
                role: "assistant",
                text: init.greeting,
                timestamp: new Date().toISOString(),
              },
            ]);
          }
        } catch {
          // Could not initialize -- show error
        }
      }

      // Load history
      try {
        const history = await api.getHistory();
        if (history.length > 0) {
          setMessages(
            history
              .filter((m) => m.role === "user" || m.role === "assistant")
              .map((m) => ({
                id: nextId(),
                role: m.role as "user" | "assistant",
                text: m.content,
                timestamp: m.created_at,
              }))
          );
        }
      } catch {
        // History unavailable
      }
    }
  }, [api, initialized]);

  const handleClose = useCallback(() => {
    setIsOpen(false);
    if (window.parent !== window) {
      window.parent.postMessage({ type: "widget:minimize" }, "*");
    }
  }, []);

  const handleSend = useCallback(() => {
    const text = inputText.trim();
    if (!text) return;

    // Add user message to UI
    setMessages((prev) => [
      ...prev,
      {
        id: nextId(),
        role: "user",
        text,
        timestamp: new Date().toISOString(),
      },
    ]);
    setInputText("");
    setIsTyping(true);

    // Send via API
    api.sendMessage(text);
  }, [api, inputText]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  // Chat bubble button (when closed)
  if (!isOpen) {
    return (
      <div id="ai-widget">
        <button
          class="widget-bubble"
          onClick={handleOpen}
          aria-label="Open chat"
        >
          <svg
            width="28"
            height="28"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </button>
      </div>
    );
  }

  // Open chat window
  return (
    <div id="ai-widget">
      <div class="widget-container">
        {/* Header */}
        <div class="widget-header">
          <div class="widget-header-info">
            <span
              class={`widget-status-dot ${isConnected ? "connected" : "disconnected"}`}
            />
            <span class="widget-header-title">AI Assistant</span>
          </div>
          <button
            class="widget-close-btn"
            onClick={handleClose}
            aria-label="Close chat"
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Messages */}
        <div class="widget-messages">
          {messages.length === 0 && !isTyping && (
            <div class="widget-empty">
              <p>Start a conversation...</p>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              class={`widget-message ${msg.role === "user" ? "widget-message-user" : "widget-message-assistant"}`}
            >
              <div class="widget-bubble-text">{msg.text}</div>
            </div>
          ))}

          {isTyping && (
            <div class="widget-message widget-message-assistant">
              <div class="widget-typing">
                <span class="widget-typing-dot" />
                <span class="widget-typing-dot" />
                <span class="widget-typing-dot" />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div class="widget-input-area">
          <input
            ref={inputRef}
            type="text"
            class="widget-input"
            placeholder="Type a message..."
            value={inputText}
            onInput={(e) => setInputText((e.target as HTMLInputElement).value)}
            onKeyDown={handleKeyDown}
          />
          <button
            class="widget-send-btn"
            onClick={handleSend}
            disabled={!inputText.trim()}
            aria-label="Send message"
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
