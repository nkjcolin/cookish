import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, idempotencyKey, isNotFound, unwrap, type Schemas } from "./client";

type Suggestion = Schemas["Suggestion"];

export const SUGGESTION_KEY = ["cook", "suggestion"];
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
      try {
        if (step.kind === "adjust") {
          return unwrap(await api.POST("/api/cook/sessions/{session_id}/adjust", { params, body: step.body }));
        }
        const path = step.kind === "next" ? "/api/cook/sessions/{session_id}/next" : "/api/cook/sessions/{session_id}/previous";
        return unwrap(await api.POST(path, { params }));
      } catch (error) {
        // The session has expired: carry on in a new one held to the same conditions.
        const current = queryClient.getQueryData<Suggestion>(SUGGESTION_KEY);
        if (!isNotFound(error) || !current) throw error;
        return startCookSession({
          ...mergeConstraints(current, step.kind === "adjust" ? step.body : null),
          skipPreviousRecipe: step.kind === "next",
        });
      }
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
    mutationFn: async () => {
      try {
        return unwrap(await api.POST("/api/cook/sessions/{session_id}/select", { params: { path: { session_id: sessionId! } } }));
      } catch (error) {
        // The session has expired. Show a fresh suggestion rather than cook one nobody chose.
        const current = queryClient.getQueryData<Suggestion>(SUGGESTION_KEY);
        if (!isNotFound(error) || !current) throw error;
        queryClient.setQueryData(SUGGESTION_KEY, await startCookSession(mergeConstraints(current, null)));
        throw new Error("That suggestion had expired, so here is a fresh one.", { cause: error });
      }
    },
    onSuccess: (record) => queryClient.setQueryData(COOK_RECORD_KEY, record),
  });
}

/** Optional free-text nudge: the ai service turns a sentence into an adjustment. */
export function useInterpret() {
  return useMutation({
    mutationFn: async (text: string) => unwrap(await api.POST("/ai/interpret", { body: { text } })),
  });
}

/** The dish chosen with "Cook this", if any. Set by useSelectSuggestion. */
export function useCookRecord() {
  const queryClient = useQueryClient();
  return queryClient.getQueryData<Schemas["CookRecord"]>(COOK_RECORD_KEY);
}

export function useCurrentSuggestion() {
  const queryClient = useQueryClient();
  return queryClient.getQueryData<Suggestion>(SUGGESTION_KEY);
}

export function useRecipe(recipeId: string | undefined) {
  return useQuery({
    queryKey: ["recipe", recipeId],
    queryFn: async () => unwrap(await api.GET("/api/recipes/{recipe_id}", { params: { path: { recipe_id: recipeId! } } })),
    enabled: recipeId !== undefined,
    staleTime: Infinity,
  });
}

/** Records what was actually used. Nothing is deducted until the user confirms here. */
export function useConfirmCook(recordId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (lines: Schemas["ConsumptionLine"][]) =>
      unwrap(
        await api.POST("/api/cook/records/{record_id}/confirm", {
          params: { path: { record_id: recordId }, header: idempotencyKey() },
          body: { lines },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["inventory"] }),
  });
}

/** One tap after the meal. Only a cooked dish can be rated. */
export function useRateCook() {
  return useMutation({
    mutationFn: async ({ recordId, rating }: { recordId: string; rating: Schemas["Rating"] }) =>
      unwrap(
        await api.POST("/api/cook/records/{record_id}/feedback", {
          params: { path: { record_id: recordId } },
          body: { rating },
        }),
      ),
  });
}

/** After a meal is confirmed: forget the finished dish and start a fresh session. */
export function useFinishCooking() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.removeQueries({ queryKey: COOK_RECORD_KEY });
    void queryClient.resetQueries({ queryKey: SUGGESTION_KEY });
  };
}

export type CookConstraints = {
  sourceSessionId?: string;
  skipPreviousRecipe?: boolean;
  people: number;
  tags: Schemas["CookTag"][];
  maxMinutes: number | null;
  maxDifficulty: number | null;
};

function tighten(existing: number | null, requested: number | null | undefined) {
  return requested == null ? existing : existing === null ? requested : Math.min(existing, requested);
}

/** The conditions the session is held to, with an adjustment (if any) added on top. */
export function mergeConstraints(suggestion: Suggestion, adjust: Schemas["CookAdjust"] | null): CookConstraints {
  const applied = suggestion.applied_constraints;
  let maxMinutes = tighten(applied.max_minutes, adjust?.max_minutes);
  let maxDifficulty = tighten(applied.max_difficulty, adjust?.max_difficulty);
  // A newly requested relative nudge refers to the dish the user saw, not the
  // first dish a replacement session happens to rank. Historical tags are labels.
  if (adjust?.tags?.includes("quicker")) maxMinutes = tighten(maxMinutes, Math.max(0, suggestion.recipe.total_minutes - 10));
  if (adjust?.tags?.includes("easier")) maxDifficulty = tighten(maxDifficulty, Math.max(0, suggestion.recipe.difficulty - 1));
  return {
    sourceSessionId: suggestion.session_id,
    people: adjust?.people ?? suggestion.people,
    tags: [...new Set([...applied.tags, ...(adjust?.tags ?? [])])],
    maxMinutes,
    maxDifficulty,
  };
}

/** Removing a relative label also removes the limit that label represents. */
export function dropCookTag(constraints: CookConstraints, tag: Schemas["CookTag"]): CookConstraints {
  return {
    ...constraints,
    tags: constraints.tags.filter((value) => value !== tag),
    maxMinutes: tag === "quicker" ? null : constraints.maxMinutes,
    maxDifficulty: tag === "easier" ? null : constraints.maxDifficulty,
  };
}

/** Omit constraints only for Reset, which returns to household preference defaults. */
async function startCookSession(input: CookConstraints | Pick<CookConstraints, "people">): Promise<Suggestion> {
  const body: Schemas["CookSessionCreate"] = { people: input.people };
  if ("tags" in input) {
    if (input.sourceSessionId) body.previous_session_id = input.sourceSessionId;
    if (input.skipPreviousRecipe) body.skip_previous_recipe = true;
    body.constraints = {
      tags: input.tags,
      max_minutes: input.maxMinutes,
      max_difficulty: input.maxDifficulty,
    };
  }
  return unwrap(await api.POST("/api/cook/sessions", { body }));
}

/**
 * Starts the session again with a reduced set of constraints. Adjustments only ever
 * accumulate on a session, so dropping one means beginning a new session with the rest.
 */
export function useRestartCook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: startCookSession,
    onSuccess: (suggestion) => queryClient.setQueryData(SUGGESTION_KEY, suggestion),
  });
}
