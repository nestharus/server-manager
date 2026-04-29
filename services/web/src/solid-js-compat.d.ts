import "solid-js";

// Aligns Solid imports with the local Solid 2 beta compatibility wrapper.
// These declarations cover the legacy createEffect initial-value shape, the
// local on helper's disposer callback, and onMount's callback-only contract.
declare module "solid-js" {
  export function createEffect<T>(effect: (previous?: T) => T | void, initial?: T): void;
  export function on<T>(
    source: () => T,
    effect: (input: T, previousInput: T | undefined) => void,
    options?: { defer?: boolean },
  ): () => void;
  export function onMount(callback: () => void): void;
}
