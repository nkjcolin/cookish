import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

/**
 * State handed over by the previous screen through the router, such as "a meal was just
 * confirmed". It is read once and then removed from the browser history, so a reload or
 * the back button does not replay it.
 */
export function useArrivalState<T>(): T | null {
  const location = useLocation();
  const navigate = useNavigate();
  const [arrival] = useState(location.state as T | null);
  useEffect(() => {
    if (location.state !== null) navigate(location.pathname, { replace: true, state: null });
  }, [location, navigate]);
  return arrival;
}

/** Arriving after an inventory change that can still be undone. */
export type KitchenChanged = { eventId: string; message: string };
