'use client';

import { useContext, useEffect, useRef, useState } from 'react';
import { RoomEvent } from 'livekit-client';
import { RoomAudioRenderer, RoomContext, StartAudio } from '@livekit/components-react';
import { useSession } from '@/components/app/session-provider';

// --------------------- ChatBox Component ---------------------
interface ChatMessage {
  id: number;
  sender: 'ai' | 'user';
  text: string;
}

interface ChatBoxProps {
  room: ReturnType<typeof useContext> | null;
}

function ChatBox({ room }: ChatBoxProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [showChat, setShowChat] = useState(false);
  const msgIdRef = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Subscribe to data messages
  useEffect(() => {
    if (!room) return;

    const handleData = (payload: Uint8Array, participant: any) => {
      const text = new TextDecoder().decode(payload);
      const sender = !participant || participant.identity.includes('agent') ? 'ai' : 'user';
      setMessages((prev) => [...prev, { id: msgIdRef.current++, sender, text }]);
    };

    room.on(RoomEvent.DataReceived, handleData);
    return () => room.off(RoomEvent.DataReceived, handleData);
  }, [room]);

  // Auto-scroll
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim() || !room?.localParticipant) return;

    room.localParticipant.publishData(new TextEncoder().encode(input.trim()));
    setMessages((prev) => [...prev, { id: msgIdRef.current++, sender: 'user', text: input }]);
    setInput('');
  };

  return (
    <div className="absolute right-6 bottom-6 flex flex-col items-end">
      <button
        className="mb-2 rounded-full bg-amber-500 p-3 text-black shadow-lg transition hover:bg-amber-600"
        onClick={() => setShowChat((v) => !v)}
      >
        {showChat ? '🙈' : '💬'}
      </button>

      {showChat && (
        <div className="flex w-[300px] flex-col rounded-lg bg-[#1c1c20]/90 p-3 shadow-xl backdrop-blur-lg">
          <div
            ref={scrollRef}
            className="mb-2 flex max-h-[350px] flex-col overflow-y-auto rounded border border-gray-700 p-2"
          >
            {messages.map((m) => (
              <div
                key={m.id}
                className={`my-1 flex ${m.sender === 'ai' ? 'justify-start' : 'justify-end'}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-3 py-2 text-sm shadow-md ${
                    m.sender === 'ai' ? 'bg-gray-800 text-gray-200' : 'bg-amber-600 text-black'
                  }`}
                >
                  {m.text}
                </div>
              </div>
            ))}
          </div>

          <div className="flex w-full gap-2">
            <input
              type="text"
              value={input}
              disabled={!room?.localParticipant}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder={room?.localParticipant ? 'Type a message...' : 'Connecting to agent...'}
              className="w-full rounded-lg bg-gray-900 px-3 py-1 text-gray-100 placeholder-gray-500 focus:outline-none"
            />
            <button
              onClick={handleSend}
              disabled={!room?.localParticipant || !input.trim()}
              className="rounded-lg bg-amber-500 px-3 py-1 text-black shadow-md transition hover:bg-amber-600 disabled:opacity-50"
            >
              ➤
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default ChatBox;

// --------------------- ChatBox Usage Example ---------------------
