import React from 'react';

type BeverageProps = {
  size: 'small' | 'medium' | 'large';
  hasCream: boolean;
};

export const BeverageRenderer = ({ size, hasCream }: BeverageProps) => {
  // Map sizes to CSS pixel heights/widths
  const sizeMap = {
    small: { height: '120px', width: '90px' },
    medium: { height: '160px', width: '110px' },
    large: { height: '200px', width: '130px' },
  };

  const { height, width } = sizeMap[size];

  return (
    <div className="flex flex-col items-center justify-center p-8 transition-all duration-500">
      <div className="relative">
        {/* Whipped Cream (conditionally rendered) */}
        {hasCream && (
          <div className="absolute -top-8 left-1/2 z-10 w-full -translate-x-1/2 animate-bounce">
            <div className="relative h-12 w-24 rounded-full bg-white shadow-md">
              <div className="absolute -top-4 left-4 h-12 w-12 rounded-full bg-white" />
              <div className="absolute -top-2 right-4 h-10 w-10 rounded-full bg-white" />
            </div>
          </div>
        )}

        {/* The Cup Body */}
        <div
          className="relative rounded-t-sm rounded-b-3xl border-4 border-white bg-amber-800 shadow-xl transition-all duration-500 ease-in-out"
          style={{ width, height }}
        >
          {/* Coffee Liquid Level */}
          <div className="absolute top-4 right-2 bottom-2 left-2 rounded-b-2xl bg-black/20" />

          {/* Reflection */}
          <div className="absolute top-4 left-3 h-full w-2 rounded-full bg-white/10" />
        </div>

        {/* Cup Handle */}
        <div className="absolute top-1/2 -right-6 -z-10 h-16 w-10 -translate-y-1/2 rounded-r-2xl border-4 border-white" />

        {/* Saucer */}
        <div className="absolute -bottom-2 left-1/2 h-4 w-[140%] -translate-x-1/2 rounded-full bg-white shadow-lg" />
      </div>

      <div className="mt-8 font-mono text-sm tracking-widest text-white/80 uppercase">
        ORDER: {size} {hasCream ? '+ CREAM' : ''}
      </div>
    </div>
  );
};
