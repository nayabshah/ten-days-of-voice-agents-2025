// types.ts

export interface OrderState {
  drinkType: string | null;
  size: 'Small' | 'Medium' | 'Large' | null;
  milk: string | null;
  extras: string[];
  name: string | null;
}

// Initial empty order
export const INITIAL_ORDER_STATE: OrderState = {
  drinkType: null,
  size: null,
  milk: null,
  extras: [],
  name: null,
};

// Utility function to update order state
export function updateOrder(currentOrder: OrderState, updates: Partial<OrderState>): OrderState {
  return {
    ...currentOrder,
    ...updates,
    // Merge extras arrays uniquely
    extras: updates.extras
      ? Array.from(new Set([...currentOrder.extras, ...updates.extras]))
      : currentOrder.extras,
  };
}
