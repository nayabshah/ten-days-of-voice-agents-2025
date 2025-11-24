import React from 'react';
import { OrderState } from './types';

interface ReceiptProps {
  order: OrderState;
}

export const Receipt: React.FC<ReceiptProps> = ({ order }) => {
  const isComplete = order.drinkType && order.size && order.milk && order.name;

  return (
    <div className="receipt-scroll w-full max-w-sm rounded-lg border-t-8 border-green-700 bg-white p-6 font-mono text-sm shadow-md">
      <div className="mb-6 text-center">
        <h2 className="text-2xl font-bold text-gray-800">GEMINI BEANS</h2>
        <p className="text-xs text-gray-500">AI POWERED COFFEE</p>
        <div className="my-4 border-b border-dashed border-gray-300"></div>
      </div>

      <div className="mb-6 space-y-3">
        <div className="flex justify-between">
          <span className="text-gray-500">Customer</span>
          <span className="max-w-[150px] truncate font-bold">{order.name || '...'}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Drink</span>
          <span className="font-bold">{order.drinkType || '...'}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Size</span>
          <span className="font-bold">{order.size || '...'}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Milk</span>
          <span className="font-bold">{order.milk || '...'}</span>
        </div>
        <div className="flex items-start justify-between">
          <span className="text-gray-500">Extras</span>
          <div className="text-right">
            {order.extras.length > 0 ? (
              order.extras.map((ex, i) => <div key={i}>{ex}</div>)
            ) : (
              <span className="text-gray-300">-</span>
            )}
          </div>
        </div>
      </div>

      <div className="my-4 border-b border-dashed border-gray-300"></div>

      <div className="text-center">
        {isComplete ? (
          <div className="flex flex-col gap-2">
            <div className="text-xl font-bold text-gray-800">TOTAL: $0.00</div>
            <p className="text-xs font-semibold tracking-wide text-green-600 uppercase">
              Ready for Pickup
            </p>
            <button
              onClick={() => {
                const blob = new Blob([JSON.stringify(order, null, 2)], {
                  type: 'application/json',
                });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `order-${order.name || 'guest'}.json`;
                a.click();
              }}
              className="mt-2 rounded bg-stone-800 px-4 py-2 text-xs text-white transition-colors hover:bg-stone-700"
            >
              Download Receipt
            </button>
          </div>
        ) : (
          <div className="animate-pulse text-xs font-semibold tracking-wide text-amber-600 uppercase">
            Taking Order...
          </div>
        )}
      </div>

      <div className="mt-8 text-center text-[10px] text-gray-400">
        Thank you for visiting Gemini Beans.
        <br />
        {new Date().toLocaleDateString()} {new Date().toLocaleTimeString()}
      </div>
    </div>
  );
};
