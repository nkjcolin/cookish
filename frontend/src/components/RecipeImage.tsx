import { useState } from "react";

import { getRecipeImage } from "../data/recipeImages";
import { Icon } from "./Icon";

type RecipeImageProps = {
  recipeId: string;
  title: string;
  className?: string;
};

/** The suggestion and recipe page resolve the same illustration from the recipe UUID. */
export function RecipeImage({ recipeId, title, className = "" }: RecipeImageProps) {
  const image = getRecipeImage(recipeId);
  const [failedSource, setFailedSource] = useState<string | null>(null);

  return (
    <div className={`overflow-hidden bg-surface-sunken ${className}`}>
      {image && failedSource !== image.src ? (
        <img
          key={image.src}
          src={image.src}
          alt={image.alt}
          className="h-full w-full object-cover"
          loading="eager"
          decoding="async"
          onError={() => setFailedSource(image.src)}
        />
      ) : (
        <div
          role="img"
          aria-label={`No image available for ${title}`}
          className="flex h-full flex-col items-center justify-center gap-[8px] text-ink-muted"
        >
          <Icon name="pot-hero" />
          <span className="text-[12px]">Recipe image unavailable</span>
        </div>
      )}
    </div>
  );
}
