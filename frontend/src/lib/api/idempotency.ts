export function createIdempotencyKey(): string {
  if (
    typeof crypto === "undefined" ||
    typeof crypto.randomUUID !== "function"
  ) {
    throw new Error("Secure random UUID support is required.");
  }
  return crypto.randomUUID();
}
