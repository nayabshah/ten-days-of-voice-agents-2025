'use client';

export function BaristaWelcomeView({ onStart }) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center">
      <h1 className="text-4xl font-bold text-amber-400">☕ AI Barista</h1>
      <p className="mt-2 text-gray-300">Your voice-powered coffee assistant</p>

      <button
        onClick={onStart}
        className="mt-6 rounded-lg bg-amber-500 px-6 py-3 font-semibold text-black hover:bg-amber-600"
      >
        🔊 Connect to Barista
      </button>
    </div>
  );
}
