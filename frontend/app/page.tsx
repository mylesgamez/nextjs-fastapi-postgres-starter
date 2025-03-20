"use client";
import { useEffect, useRef, useState } from "react";

type Message = {
  id?: number;
  sender: "user" | "bot";
  content: string;
};

export default function Home() {
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const socketRef = useRef<WebSocket | null>(null);
  const [hasCreatedConvo, setHasCreatedConvo] = useState(false);

  const baseUrl =
    process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  useEffect(() => {
    const storedId = localStorage.getItem("conversationId");
    if (storedId) {
      console.log("Found existing conversation ID in localStorage:", storedId);
      setConversationId(parseInt(storedId, 10));
    } else {
      console.log("No conversation in localStorage, creating new...");
      fetch(`${baseUrl}/conversations/new`, {
        method: "POST",
      })
        .then((res) => res.json())
        .then((data) => {
          const newId = data.conversation_id as number;
          localStorage.setItem("conversationId", String(newId));
          setConversationId(newId);
          console.log("Created conversation id:", newId);
        })
        .catch((err) => {
          console.error("Failed to create conversation:", err);
        });
    }
  }, [baseUrl]);

  useEffect(() => {
    if (conversationId == null) return;

    console.log("Fetching messages for convo:", conversationId);
    fetch(`${baseUrl}/conversations/${conversationId}/messages`)
      .then((res) => res.json())
      .then((msgs: any[]) => {
        const loaded = msgs.map((m) => ({
          id: m.id,
          sender: m.sender === "user" ? "user" : "bot",
          content: m.content,
        })) as Message[];
        console.log("Loaded messages from DB:", loaded);
        setMessages(loaded);
      })
      .catch((err) => {
        console.error("Failed to fetch conversation messages:", err);
      });
  }, [conversationId, baseUrl]);

  useEffect(() => {
    if (conversationId == null) return;

    const wsUrl = baseUrl.replace(/^http/, "ws") + `/ws/chat?conversation_id=${conversationId}`;
    console.log("Opening WebSocket for conversation:", conversationId, wsUrl);
    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onopen = () => {
      console.log("WebSocket connected to conversation:", conversationId);
    };

    ws.onmessage = (event) => {
      console.log("WS received:", event.data);
      const botMsg: Message = { sender: "bot", content: event.data };
      setMessages((prev) => [...prev, botMsg]);
    };

    ws.onclose = () => {
      console.log("WebSocket closed");
    };

    ws.onerror = (err) => {
      console.error("WebSocket error", err);
    };

    return () => {
      console.log("Cleaning up WebSocket...");
      ws.close();
    };
  }, [conversationId, baseUrl]);

  const sendMessage = () => {
    if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
      alert("WebSocket not connected!");
      return;
    }
    const text = input.trim();
    if (!text) return;

    console.log("Sending user message:", text);
    setMessages((prev) => [...prev, { sender: "user", content: text }]);
    socketRef.current.send(text);
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <main className="min-h-screen bg-gray-100 flex flex-col items-center p-4">
      <div className="w-full max-w-md bg-white shadow-md rounded p-4 flex flex-col flex-grow">
        <h1 className="text-xl font-bold mb-2">Simplified Chatbot</h1>

        <p className="text-sm text-gray-500 mb-2">
          Conversation ID: {conversationId ?? "(loading...)"}
        </p>

        <div className="flex-1 overflow-auto mb-2 border p-2">
          {messages.length > 0 ? (
            messages.map((msg, idx) => (
              <div
                key={idx}
                className={`mb-2 flex ${
                  msg.sender === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`rounded px-3 py-2 max-w-xs ${
                    msg.sender === "user"
                      ? "bg-blue-500 text-white"
                      : "bg-gray-300 text-black"
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))
          ) : (
            <div className="text-gray-500">No messages yet. Say hello!</div>
          )}
        </div>

        <div className="flex items-center gap-2">
          <input
            className="border border-gray-300 rounded p-2 flex-1"
            placeholder="Type a message..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button
            className="bg-blue-600 text-white px-4 py-2 rounded"
            onClick={sendMessage}
          >
            Send
          </button>
        </div>
      </div>
    </main>
  );
}
