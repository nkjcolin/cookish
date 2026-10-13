import type { ButtonHTMLAttributes } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary";
};

export function Button({ variant = "primary", className = "", type = "button", ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={`flex h-[52px] items-center justify-center rounded-md px-[22px] text-[15px] font-bold whitespace-nowrap disabled:opacity-50 ${
        variant === "primary" ? "bg-primary text-white" : "border border-border bg-surface text-ink"
      } ${className}`}
      {...props}
    />
  );
}
