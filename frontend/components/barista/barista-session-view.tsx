'use client';

import ChatBox from '@/components/chat/chat-box';

export function BaristaSessionView({ onDisconnect }) {
  return (
    <div className="relative flex w-full flex-col p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-bold text-amber-400">☕ Talking to Barista</h2>

        <button
          onClick={onDisconnect}
          className="rounded-lg bg-red-600 px-4 py-2 text-white hover:bg-red-700"
        >
          🔇 Disconnect
        </button>
      </div>

      <ChatBox />
    </div>
  );
}
