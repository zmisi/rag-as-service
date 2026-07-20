"use client";

import type { Message } from "@/lib/api";

type Props = {
  messages: Message[];
  emptyHint: string;
};

export function MessageList({ messages, emptyHint }: Props) {
  if (messages.length === 0) {
    return <div className="messages empty">{emptyHint}</div>;
  }

  return (
    <div className="messages">
      {messages.map((m) => (
        <article key={m.id} className={`bubble role-${m.role}`}>
          <header className="bubble-meta">{m.role}</header>
          <p className="bubble-body">{m.content}</p>
        </article>
      ))}
    </div>
  );
}
