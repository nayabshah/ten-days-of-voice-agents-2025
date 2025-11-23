// components/AudioListener.tsx
'use client';

export function AudioListener({ listening }: { listening: boolean }) {
  return (
    <div className="flex flex-col items-center gap-3">
      {/* Pulsing circle */}
      <div
        className={`relative flex h-20 w-20 items-center justify-center rounded-full transition-all duration-300 ${listening ? 'animate-pulse-bg' : 'bg-gray-700/40'} `}
      >
        <div
          className={`flex h-14 w-14 items-center justify-center rounded-full bg-amber-500 shadow-xl transition-all duration-300 ${listening ? 'scale-110' : 'scale-100'} `}
        >
          🎤
        </div>
      </div>

      {/* Waveform bars */}
      <div className="flex h-5 gap-1">
        {[1, 2, 3, 4, 5].map((bar) => (
          <div
            key={bar}
            className={`w-1 rounded-full bg-amber-400 ${listening ? `animate-wave-${bar}` : 'h-2 opacity-30'} `}
          />
        ))}
      </div>
    </div>
  );
}
