import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap, type Schemas } from "./client";

type Suggestion = Schemas["Suggestion"];

const SUGGESTION_KEY = ["cook", "suggestion"];
export const COOK_RECORD_KEY = ["cook", "record"];

/**
 * The current Cook session. It starts the first time the Cook tab opens and then lives
 * in the cache, so leaving the tab and coming back shows the same suggestion.
 */
export function useCookSuggestion() {
  return useQuery({
    queryKey: SUGGESTION_KEY,
    queryFn: async () => unwrap(await api.POST("/api/cook/sessions", { body: {} })),
    staleTime: Infinity,
    gcTime: Infinity,
    retry: false,
  });
}

type Step = { kind: "next" } | { kind: "previous" } | { kind: "adjust"; body: Schemas["CookAdjust"] };

/** "Not tonight", "Previous one" and every nudge: each returns the suggestion to show next. */
export function useCookStep(sessionId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (step: Step): Promise<Suggestion> => {
      const params = { path: { session_id: sessionId! } };
      if (step.kind === "adjust") {
        return unwrap(await api.POST("/api/cook/sessions/{session_id}/adjust", { params, body: step.body }));
      }
      const path = step.kind === "next" ? "/api/cook/sessions/{session_id}/next" : "/api/cook/sessions/{session_id}/previous";
      return unwrap(await api.POST(path, { params }));
    },
    onSuccess: (suggestion) => queryClient.setQueryData(SUGGESTION_KEY, suggestion),
  });
}

export function useStarRecipe() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ recipeId, starred }: { recipeId: string; starred: boolean }) =>
      unwrap(await api.PUT("/api/recipes/{recipe_id}/star", { params: { path: { recipe_id: recipeId } }, body: { starred } })),
    onSuccess: (result) =>
      queryClient.setQueryData<Suggestion>(SUGGESTION_KEY, (current) =>
        current && current.recipe.id === result.recipe_id
          ? { ...current, recipe: { ...current.recipe, starred: result.starred } }
          : current,
      ),
  });
}

/** "Cook this": creates the cook record that the recipe and what's-left screens work on. */
export function useSelectSuggestion(sessionId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.POST("/api/cook/sessions/{session_id}/select", { params: { path: { session_id: sessionId! } } })),
    onSuccess: (record) => queryClient.setQueryData(COOK_RECORD_KEY, record),
  });
}

/** Optional free-text nudge: the ai service turns a sentence into an adjustment. */
export function useInterpret() {
  return useMutation({
    mutationFn: async (text: string) => unwrap(await api.POST("/ai/interpret", { body: { text } })),
  });
}
