'use client';

import { RoomAudioRenderer, StartAudio } from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { SessionProvider } from '@/components/app/session-provider';
import { ViewController } from '@/components/app/view-controller';
import BaristaClient from '@/components/barista-client';
import { Toaster } from '@/components/livekit/toaster';

interface AppProps {
  baristaConfig: AppConfig;
}

export function BaristaPage({ baristaConfig }: AppProps) {
  return (
    <SessionProvider appConfig={baristaConfig}>
      <main className="grid h-svh grid-cols-1 place-content-center">
        <BaristaClient />
      </main>
      <StartAudio label="Start Audio" />
      <RoomAudioRenderer />
      <Toaster />
    </SessionProvider>
  );
}
