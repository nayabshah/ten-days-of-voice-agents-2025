import React from 'react';
import { OrderState } from './types';

interface CoffeeCupProps {
  order: OrderState;
}

export const CoffeeCup: React.FC<CoffeeCupProps> = ({ order }) => {
  const { size, drinkType, extras, milk } = order;

  // Size mapping
  const sizeClasses = {
    Small: 'h-32 w-28',
    Medium: 'h-48 w-36',
    Large: 'h-64 w-44',
  };
  const currentSizeClass = size ? sizeClasses[size] : 'h-40 w-32'; // Default to something in between

  // Drink color mapping
  const getDrinkColor = () => {
    if (!drinkType) return 'bg-stone-300'; // Empty/Unknown
    const lowerType = drinkType.toLowerCase();
    if (lowerType.includes('latte') || lowerType.includes('milk')) return 'bg-[#C8A27A]'; // Light brown
    if (lowerType.includes('cappuccino')) return 'bg-[#A88B68]'; // Med brown
    if (lowerType.includes('espresso') || lowerType.includes('black')) return 'bg-[#3C2A20]'; // Dark brown
    if (lowerType.includes('matcha')) return 'bg-green-200';
    return 'bg-[#6F4E37]'; // Generic coffee
  };

  const hasWhippedCream = extras.some(
    (e) => e.toLowerCase().includes('whipped') || e.toLowerCase().includes('cream')
  );
  const isIced =
    drinkType?.toLowerCase().includes('ice') || extras.some((e) => e.toLowerCase().includes('ice'));

  return (
    <div className="relative flex h-96 w-64 flex-col items-center justify-end transition-all duration-500">
      {/* Steam or Ice */}
      {!isIced && drinkType && (
        <div className="absolute -top-10 flex space-x-2 opacity-50">
          <div className="steam h-10 w-2 rounded-full bg-gray-400 blur-md"></div>
          <div className="steam h-12 w-2 rounded-full bg-gray-400 blur-md"></div>
          <div className="steam h-8 w-2 rounded-full bg-gray-400 blur-md"></div>
        </div>
      )}

      {/* Whipped Cream */}
      {hasWhippedCream && (
        <div
          className="absolute z-20 -mt-10 flex flex-col items-center transition-all duration-500"
          style={{
            bottom:
              size === 'Large'
                ? '16rem'
                : size === 'Medium'
                  ? '12rem'
                  : size === 'Small'
                    ? '8rem'
                    : '10rem',
          }}
        >
          <div className="mb-[-15px] h-10 w-20 rounded-full bg-white shadow-sm"></div>
          <div className="mb-[-15px] h-10 w-14 rounded-full bg-white shadow-sm"></div>
          <div className="h-8 w-8 rounded-full bg-white shadow-sm"></div>
        </div>
      )}

      {/* Cup Body */}
      <div
        className={`${currentSizeClass} relative flex items-end justify-center overflow-hidden rounded-b-3xl border-2 border-gray-200 bg-white shadow-lg transition-all duration-500`}
      >
        {/* Liquid */}
        <div
          className={`w-full ${getDrinkColor()} relative transition-colors duration-500`}
          style={{ height: '90%' }}
        >
          {/* Milk Foam/Layer for visual interest */}
          {milk && !milk.toLowerCase().includes('none') && (
            <div className="absolute top-0 h-4 w-full bg-white opacity-20 blur-sm"></div>
          )}
          {/* Ice Cubes */}
          {isIced && (
            <div className="absolute inset-0 flex flex-wrap content-end gap-2 p-4 opacity-60">
              <div className="h-6 w-6 rotate-12 transform rounded-md bg-white"></div>
              <div className="h-6 w-6 -rotate-6 transform rounded-md bg-white"></div>
              <div className="h-6 w-6 rotate-45 transform rounded-md bg-white"></div>
            </div>
          )}
        </div>

        {/* Cup Label/Logo */}
        <div className="absolute top-1/2 left-1/2 z-10 flex h-12 w-12 -translate-x-1/2 -translate-y-1/2 transform items-center justify-center rounded-full border-2 border-green-700 bg-white">
          <div className="text-center text-[8px] leading-tight font-bold text-green-700">
            GEMINI
            <br />
            BEANS
          </div>
        </div>

        {/* Cup Sleeve (only for hot drinks usually, but let's add for aesthetics if it's not small) */}
        {size !== 'Small' && !isIced && (
          <div className="absolute bottom-6 h-12 w-[102%] bg-amber-700 opacity-90"></div>
        )}
      </div>

      {/* Cup Shadow */}
      <div className="mt-4 h-4 w-32 rounded-full bg-black opacity-10 blur-sm"></div>
    </div>
  );
};
