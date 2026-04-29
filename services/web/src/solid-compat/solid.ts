// @ts-nocheck
import * as solid from "../../node_modules/solid-js/dist/solid.js";

export * from "../../node_modules/solid-js/dist/solid.js";

export function batch<T>(callback: () => T): T {
  return callback();
}

export const equalFn = <T>(a: T, b: T) => a === b;

export function Suspense(props: { readonly children?: unknown; readonly fallback?: unknown }) {
  return props.children ?? props.fallback ?? null;
}

export function ErrorBoundary(props: { readonly children?: unknown; readonly fallback?: unknown }) {
  return props.children ?? props.fallback ?? null;
}

export function startTransition(callback: () => void) {
  callback();
}

export function useTransition() {
  return [() => false, startTransition] as const;
}

export function mergeProps<T extends object[]>(...sources: T): T[number] {
  return Object.assign({}, ...sources);
}

export function splitProps<T extends Record<string, unknown>, K extends readonly (keyof T)[]>(
  props: T,
  ...keyGroups: K[]
) {
  const used = new Set<keyof T>();
  const groups = keyGroups.map((keys) => {
    const output: Partial<T> = {};
    for (const key of keys) {
      used.add(key);
      if (key in props) {
        output[key] = props[key];
      }
    }
    return output;
  });
  const rest: Partial<T> = {};
  for (const key of Object.keys(props) as (keyof T)[]) {
    if (!used.has(key)) {
      rest[key] = props[key];
    }
  }
  return [...groups, rest];
}

export function Index<T>(props: {
  readonly each: readonly T[] | undefined | null;
  readonly children: (item: () => T, index: number) => unknown;
}) {
  return solid.createComponent(solid.For, {
    get each() {
      return props.each ?? [];
    },
    children: (item: T, index: () => number) => props.children(() => item, index()),
  });
}

export function onMount(callback: () => void) {
  return createEffect(() => {
    callback();
  });
}

function createLegacyEffect<T>(effect: (previous?: T) => T | void, initial?: T) {
  let hasPrevious = arguments.length > 1;
  let previous = initial;
  return solid.createEffect(
    () => {
      const result = effect(hasPrevious ? previous : undefined);
      previous = result;
      hasPrevious = true;
      return result;
    },
    {
      // Solid 2 expects an effect-handler-shaped option here; the no-op keeps
      // legacy createEffect(fn, initialValue) side-effect free outside fn.
      effect: () => undefined,
    },
  );
}

function isNativeEffectHandler(value: unknown) {
  return (
    typeof value === "function" ||
    (value !== null &&
      typeof value === "object" &&
      ("effect" in value || "error" in value))
  );
}

// Dispatches legacy createEffect(fn, initialValue) through createLegacyEffect
// while preserving native Solid 2 createEffect(fn, effectHandler, options).
export function createEffect<T>(
  effect: (previous?: T) => T | void,
  initialOrEffect?: T | ((value: T, previous?: T) => void),
  options?: unknown,
) {
  if (arguments.length === 1) {
    return createLegacyEffect(effect);
  }
  if (!isNativeEffectHandler(initialOrEffect)) {
    return createLegacyEffect(effect, initialOrEffect as T);
  }
  return solid.createEffect(effect, initialOrEffect, options);
}

export const createComputed = createEffect;

export function createRenderEffect<T>(
  effect: (previous?: T) => T | void,
  initialOrEffect?: T | ((value: T, previous?: T) => void),
  options?: unknown,
) {
  if (arguments.length === 1) {
    return createLegacyEffect(effect);
  }
  if (!isNativeEffectHandler(initialOrEffect)) {
    return createLegacyEffect(effect, initialOrEffect as T);
  }
  return solid.createRenderEffect(effect, initialOrEffect, options);
}

export function on<T>(
  source: () => T,
  effect: (input: T, previousInput: T | undefined) => void,
  options?: { defer?: boolean },
) {
  let initialized = false;
  let previous: T | undefined;
  return () => {
    const input = source();
    if (initialized || !options?.defer) {
      effect(input, previous);
    }
    initialized = true;
    previous = input;
  };
}

export function createResource<T>(fetcher: () => Promise<T>) {
  const [value, setValue] = solid.createSignal<T | undefined>(undefined);
  const [loading, setLoading] = solid.createSignal(true);
  const [error, setError] = solid.createSignal<unknown>(undefined);

  solid.createEffect(() => {
    setLoading(true);
    fetcher()
      .then((result) => {
        setValue(() => result);
        setError(undefined);
      })
      .catch(setError)
      .finally(() => setLoading(false));
  });

  return [
    Object.assign(value, {
      loading,
      error,
    }),
    {
      refetch: () => fetcher().then((result) => setValue(() => result)),
    },
  ] as const;
}
