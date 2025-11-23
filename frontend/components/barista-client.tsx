'use client';

import { useCallback, useContext, useEffect, useRef, useState } from 'react';
import { RoomEvent } from 'livekit-client';
import { RoomAudioRenderer, RoomContext, StartAudio } from '@livekit/components-react';
import { useSession } from '@/components/app/session-provider';
import { BaristaUI } from './barista-ui';
import ChatBox from './chat/chat-box';

interface Message {
  id: number;
  sender: 'user' | 'ai';
  text: string;
}
// --------------------- BaristaClient Component ---------------------
export default function BaristaClient(onDisconnect?: () => void) {
  const room = useContext(RoomContext);
  const [messages, setMessages] = useState<Message[]>([]);
  const { isSessionActive, startSession, endSession } = useSession();
  const msgIdRef = useRef(0);

  useEffect(() => {
    if (!room) return;

    const onData = (payload: Uint8Array, participant?: any) => {
      const text = new TextDecoder().decode(payload);
      const sender = !participant || participant.identity.includes('agent') ? 'ai' : 'user';
      setMessages((prev) => [...prev, { id: msgIdRef.current++, sender, text }]);
    };

    room.on(RoomEvent.DataReceived, onData);
    return () => room.off(RoomEvent.DataReceived, onData);
  }, [room]);
  const handleSendMessage = (text: string) => {
    if (!room) return;
    // Send message to the room
    room.localParticipant.publishData(new TextEncoder().encode(text));
    setMessages((prev) => [...prev, { id: msgIdRef.current++, sender: 'user', text }]);
  };

  const handleDisconnect = useCallback(async () => {
    endSession();
  }, [endSession]);
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-[#0d0d0f] to-[#1a1a1d] p-6 text-gray-100">
      {/* Header */}
      <div className="mb-6 text-center">
        <h1 className="text-4xl font-extrabold text-amber-400 drop-shadow-md">
          ☕ Moonbeam Coffee
        </h1>
        <p className="mt-1 text-gray-400">Your friendly AI Barista — ready to take your order.</p>
      </div>

      {/* Connect / Disconnect */}
      <div className="mb-6 flex gap-4">
        {!isSessionActive ? (
          <button
            onClick={startSession}
            className="rounded-lg bg-amber-500 px-5 py-2 font-semibold text-black shadow-md transition hover:bg-amber-600"
          >
            🔊 Connect to Barista
          </button>
        ) : (
          <button
            onClick={handleDisconnect}
            className="rounded-lg bg-red-600 px-5 py-2 font-semibold text-white shadow-md transition hover:bg-red-700"
          >
            🔇 Disconnect
          </button>
        )}
      </div>

      {/* Voice + Audio */}
      {isSessionActive && (
        <>
          <StartAudio label="Start Microphone" />
          <RoomAudioRenderer />
        </>
      )}

      {/* Chat */}
      {isSessionActive && room && (
        <>
          {' '}
          <BaristaUI />
          <div className="w-full max-w-xl">
            <ChatBox messages={messages} onSend={handleSendMessage} />
          </div>
        </>
      )}
    </div>
  );
}
