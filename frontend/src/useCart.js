import { useEffect, useMemo, useState } from "react";

const CART_STORAGE_KEY = "food-order-cart";
const TAX_RATE = 0.05;

function getCartKey(item) {
  return item.cartKey || `${item.restaurant_name || "Default"}::${item.name}`;
}

function readStoredCart() {
  try {
    return JSON.parse(window.localStorage.getItem(CART_STORAGE_KEY)) || {};
  } catch {
    return {};
  }
}

export function useCart(menuItems) {
  const [quantities, setQuantities] = useState(readStoredCart);

  useEffect(() => {
    window.localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(quantities));
  }, [quantities]);

  const setQuantity = (itemName, nextQuantity) => {
    setQuantities((current) => {
      const safeQuantity = Math.max(0, nextQuantity);
      const next = { ...current };
      if (safeQuantity === 0) {
        delete next[itemName];
      } else {
        next[itemName] = safeQuantity;
      }
      return next;
    });
  };

  const increment = (itemName) => {
    setQuantities((current) => ({
      ...current,
      [itemName]: (current[itemName] || 0) + 1,
    }));
  };

  const decrement = (itemName) => {
    setQuantities((current) => {
      const nextQuantity = Math.max(0, (current[itemName] || 0) - 1);
      const next = { ...current };
      if (nextQuantity === 0) {
        delete next[itemName];
      } else {
        next[itemName] = nextQuantity;
      }
      return next;
    });
  };

  const remove = (itemName) => setQuantity(itemName, 0);
  const clear = () => setQuantities({});

  const items = useMemo(
    () =>
      menuItems
        .filter((item) => quantities[getCartKey(item)] > 0)
        .map((item) => ({
          ...item,
          cartKey: getCartKey(item),
          quantity: quantities[getCartKey(item)],
          subtotal: quantities[getCartKey(item)] * Number(item.price),
        })),
    [menuItems, quantities]
  );

  const summary = useMemo(() => {
    const subtotal = items.reduce((sum, item) => sum + item.subtotal, 0);
    const totalItems = items.reduce((sum, item) => sum + item.quantity, 0);
    const tax = subtotal * TAX_RATE;
    const total = subtotal + tax;
    const prepTime = totalItems ? Math.max(15, Math.min(45, 10 + totalItems * 5)) : 0;
    return { subtotal, tax, total, totalItems, prepTime };
  }, [items]);

  return { quantities, items, summary, increment, decrement, remove, clear };
}
