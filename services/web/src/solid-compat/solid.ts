// @ts-nocheck
import * as solid from "../../node_modules/solid-js/dist/solid.js";

export * from "../../node_modules/solid-js/dist/solid.js";
export type { Accessor } from "solid-js";

export const createRoot: typeof import("solid-js").createRoot = solid.createRoot;
export const createSignal: typeof import("solid-js").createSignal = ((...args: unknown[]) => {
  return solid.createSignal(...args);
}) as typeof import("solid-js").createSignal;
export const flush: typeof import("solid-js").flush = solid.flush;

export const For: typeof import("solid-js").For = solid.For;
export const Show: typeof import("solid-js").Show = solid.Show;

export function createContext<T>(defaultValue?: T, options?: unknown) {
  const context = solid.createContext(defaultValue, options);
  return Object.assign(context, { Provider: context });
}

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

function legacyEffectHandler(_value: unknown): void {}

function normalizeNativeEffectHandler<T>(handler: T): T {
  if (typeof handler === "function") {
    return ((value: unknown, previous: unknown) => {
      const cleanup = (handler as (value: unknown, previous?: unknown) => unknown)(value, previous);
      return typeof cleanup === "function" ? cleanup : undefined;
    }) as T;
  }
  if (
    handler !== null &&
    typeof handler === "object" &&
    "effect" in handler &&
    typeof (handler as { effect?: unknown }).effect === "function"
  ) {
    const bundle = handler as { effect: (value: unknown, previous?: unknown) => unknown };
    return {
      ...handler,
      effect: (value: unknown, previous: unknown) => {
        const cleanup = bundle.effect(value, previous);
        return typeof cleanup === "function" ? cleanup : undefined;
      },
    };
  }
  return handler;
}

function createLegacyEffect<T>(
  nativeCreateEffect: typeof solid.createEffect,
  effect: (previous?: T) => T | void,
  initial?: T,
) {
  let hasPrevious = arguments.length > 2;
  let previous = initial;
  return nativeCreateEffect(() => {
    const result = effect(hasPrevious ? previous : undefined);
    previous = result;
    hasPrevious = true;
    return result;
  }, legacyEffectHandler);
}

// Legacy initial values that look exactly like Solid 2 effect handlers are
// routed to the native path; callers should avoid effect/error function keys.
function isNativeEffectHandler(value: unknown) {
  return (
    typeof value === "function" ||
    (value !== null &&
      typeof value === "object" &&
      (("effect" in value && typeof (value as { effect?: unknown }).effect === "function") ||
        ("error" in value && typeof (value as { error?: unknown }).error === "function")))
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
    return createLegacyEffect(solid.createEffect, effect);
  }
  if (!isNativeEffectHandler(initialOrEffect)) {
    return createLegacyEffect(solid.createEffect, effect, initialOrEffect as T);
  }
  return solid.createEffect(effect, normalizeNativeEffectHandler(initialOrEffect), options);
}

export const createComputed = createEffect;

export function createRenderEffect<T>(
  effect: (previous?: T) => T | void,
  initialOrEffect?: T | ((value: T, previous?: T) => void),
  options?: unknown,
) {
  if (arguments.length === 1) {
    return createLegacyEffect(solid.createRenderEffect, effect);
  }
  if (!isNativeEffectHandler(initialOrEffect)) {
    return createLegacyEffect(solid.createRenderEffect, effect, initialOrEffect as T);
  }
  return solid.createRenderEffect(effect, normalizeNativeEffectHandler(initialOrEffect), options);
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

  createLegacyEffect(solid.createEffect, () => {
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
