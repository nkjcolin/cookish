import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "./client";

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async () => unwrap(await api.GET("/api/me")),
  });
}

export function useInventory() {
  return useQuery({
    queryKey: ["inventory"],
    queryFn: async () => unwrap(await api.GET("/api/inventory")),
  });
}
