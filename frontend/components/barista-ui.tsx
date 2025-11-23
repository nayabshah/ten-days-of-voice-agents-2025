'use client';

import { useEffect, useRef, useState } from 'react';
import { useRoomContext } from '@livekit/components-react';

export function BaristaUI() {
  const room = useRoomContext();

  const [showChat, setShowChat] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const msgIdRef = useRef(0);

  // Listen for data from AI agent

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-[#0d0d0f] to-[#1a1a1d] p-6 text-gray-100">
      {/* HEADER */}
      <div className="mb-6 text-center">
        <h1 className="text-4xl font-extrabold text-amber-400 drop-shadow-md">
          ☕ Moonbeam Coffee
        </h1>
        <p className="mt-1 text-gray-400">Your friendly AI Barista — ready to take your order.</p>
      </div>

      {/* VOICE + CHAT CONTROLS */}
      <div className="mb-6 flex items-center gap-4">
        {/* Voice / Mic Button */}
        <button
          className={`flex h-16 w-16 items-center justify-center rounded-full text-3xl shadow-xl transition ${
            isListening ? 'bg-red-600 hover:bg-red-700' : 'bg-amber-500 hover:bg-amber-600'
          }`}
          onClick={() => setIsListening(!isListening)}
        >
          {isListening ? '🔇' : '🎤'}
        </button>
      </div>
    </div>
  );
}
