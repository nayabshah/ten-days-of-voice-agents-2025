'use client';

import React, { useEffect, useState } from 'react';
import { Participant, RoomEvent } from 'livekit-client';
import { Track } from 'livekit-client';
import { Mic } from 'lucide-react';
import { useRoomContext } from '@livekit/components-react';
import { CoffeeCup } from './CoffeeCup';
import { Receipt } from './Receipt';
import { useSession } from './app/session-provider';
import { AgentControlBar } from './livekit/agent-control-bar/agent-control-bar';
import { INITIAL_ORDER_STATE, OrderState } from './types';

export default function BaristaClient() {
  const { isSessionActive, startSession, endSession } = useSession();
  const room = useRoomContext();

  const [order, setOrder] = useState<OrderState>(INITIAL_ORDER_STATE);
  const [finalOrder, setFinalOrder] = useState(null);

  /* -------------------------------------------------------------------------- */
  /*                        1. Handle AGENT → CLIENT updates                     */
  /*                (via metadata & attributes — NO TEXT STREAMS)               */
  /* -------------------------------------------------------------------------- */

  useEffect(() => {
    if (!room) return;

    /** ATTRIBUTE CHANGES (partial updates) */
    const handleAttrChange = (changed: Record<string, string>, participant: Participant) => {
      if (participant.isLocal) return;

      if (changed.order_update) {
        try {
          const partial = JSON.parse(changed.order_update);
          setOrder((prev) => ({ ...prev, ...partial }));
        } catch (err) {
          console.error('Bad order_update attribute:', err);
        }
      }

      if (changed.order_final) {
        try {
          const full = JSON.parse(changed.order_final);
          setFinalOrder(full);
          setOrder(full);
        } catch (err) {
          console.error('Bad order_final attribute:', err);
        }
      }
    };

    /** METADATA CHANGES (full state drops) */
    const handleMetadataChange = (oldMeta: string | undefined, participant: Participant) => {
      if (participant.isLocal) return;
      if (!participant.metadata) return;

      try {
        const meta = JSON.parse(participant.metadata);

        if (meta.partial) {
          setOrder(meta.partial);
        }

        if (meta.final) {
          setFinalOrder(meta.final);
          setOrder(meta.final);
        }
      } catch (err) {
        console.error('Bad metadata payload:', err);
      }
    };

    room.on(RoomEvent.ParticipantAttributesChanged, handleAttrChange);
    room.on(RoomEvent.ParticipantMetadataChanged, handleMetadataChange);

    return () => {
      room.off(RoomEvent.ParticipantAttributesChanged, handleAttrChange);
      room.off(RoomEvent.ParticipantMetadataChanged, handleMetadataChange);
    };
  }, [room]);

  /* -------------------------------------------------------------------------- */
  /*                                END SESSION                                 */
  /* -------------------------------------------------------------------------- */

  const handleEndSession = async () => {
    try {
      room?.localParticipant.setMicrophoneEnabled(false);
    } catch (_) {}

    endSession();
    setOrder(INITIAL_ORDER_STATE);
    setFinalOrder(null);
  };

  /* -------------------------------------------------------------------------- */
  /*                                  UI (unchanged)                             */
  /* -------------------------------------------------------------------------- */

  return (
    <div className="flex h-screen flex-col bg-[#FDFBF7]">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex items-center gap-2 text-green-800">
          <div className="rounded-lg bg-green-100 p-2">
            <span className="text-xl font-black">GB</span>
          </div>
          <h1 className="text-xl font-bold tracking-tight">GEMINI BARISTA</h1>
        </div>
        <div className="flex items-center gap-4">
          <div
            className={`flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${
              isSessionActive ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
            }`}
          >
            <div
              className={`h-2 w-2 rounded-full ${
                isSessionActive ? 'animate-pulse bg-green-500' : 'bg-gray-400'
              }`}
            ></div>
            {isSessionActive ? 'Live Agent Active' : 'Offline'}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex flex-1 flex-col overflow-hidden md:flex-row">
        <div className="relative flex flex-1 flex-col items-center justify-center overflow-hidden bg-[#F4EFEA] p-8">
          <div className="relative z-10 scale-90 transform transition-transform duration-500 md:scale-100 lg:scale-110">
            <CoffeeCup order={order} />
          </div>
        </div>

        <div className="relative z-20 mx-auto flex w-full max-w-md flex-1 flex-col border-l border-gray-200 bg-white shadow-xl md:mx-0 md:w-auto">
          <div className="flex flex-1 flex-col items-center justify-center overflow-y-auto bg-gray-50 p-6">
            <Receipt order={order} />
          </div>

          <div className="border-t border-gray-100 bg-white p-6">
            {isSessionActive && room ? (
              <AgentControlBar
                className="w-full"
                controls={{
                  leave: true,
                  chat: true,
                  camera: true,
                  microphone: true,
                  screenShare: true,
                }}
                onDisconnect={handleEndSession}
              />
            ) : (
              <button
                onClick={() => startSession()}
                className="flex w-full items-center justify-center gap-3 rounded-xl bg-stone-900 py-4 text-lg font-bold text-white shadow-lg hover:bg-stone-800"
              >
                <Mic className="h-6 w-6" />
                Start Conversation
              </button>
            )}

            <p className="mt-4 text-center text-xs text-gray-400">
              Microphone access required. Best experienced with headphones.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
