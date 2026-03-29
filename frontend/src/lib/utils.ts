import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(value: number, decimals = 2): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function formatPercent(value: number, decimals = 2): string {
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(decimals)}%`;
}

export function formatTime(isoString: string): string {
  return new Date(isoString).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

export function confidenceColor(confidence: number): string {
  if (confidence >= 0.75) return "text-neon-green";
  if (confidence >= 0.55) return "text-neon-yellow";
  return "text-neon-red";
}

export function sentimentColor(score: number): string {
  if (score > 0.1) return "text-neon-green";
  if (score < -0.1) return "text-neon-red";
  return "text-text-secondary";
}

export function generateId(): string {
  return crypto.randomUUID().replace(/-/g, "").slice(0, 16);
}
