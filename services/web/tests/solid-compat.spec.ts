import { expect, test } from "@playwright/test";
import * as solid from "../src/solid-compat/solid";

function flush() {
  solid.flush();
}

async function withRoot<T>(setup: () => T, check: (value: T) => unknown | Promise<unknown>) {
  let value: T;
  const dispose = solid.createRoot((dispose) => {
    value = setup();
    return dispose;
  });
  try {
    await check(value!);
  } finally {
    dispose();
  }
}

async function expectRunsOnce(register: (effect: () => void) => unknown) {
  let runs = 0;
  await withRoot(
    () => register(() => runs++),
    () => {
      flush();
      expect(runs).toBe(1);
    },
  );
}

async function expectPrevious(
  register: (effect: (prior?: string) => string, initial: string) => unknown,
  initial: string,
  prefix: string,
  expected: string[],
) {
  const previous: Array<string | undefined> = [];
  await withRoot(
    () => {
      const [source, setSource] = solid.createSignal(0);
      register((prior) => (previous.push(prior), `${prefix}-${source()}`), initial);
      return setSource;
    },
    (setSource) => {
      flush();
      setSource(1);
      flush();
      expect(previous).toEqual(expected);
    },
  );
}

async function expectNative(
  register: (effect: () => string, handler: (value: string) => void) => unknown,
  value: string,
) {
  const handled: string[] = [];
  await withRoot(
    () => register(() => value, (handledValue) => handled.push(handledValue)),
    () => {
      flush();
      expect(handled).toEqual([value]);
    },
  );
}

test("createEffect(fn) does not throw and runs the effect", async () => {
  await expectRunsOnce((effect) => solid.createEffect(effect));
});

test("createEffect(fn, initialValue) passes initial then previous", async () => {
  await expectPrevious(
    (effect, initial) => solid.createEffect(effect, initial),
    "initial",
    "result",
    ["initial", "result-0"],
  );
});

test("createEffect(fn, nativeHandler) takes the native path", async () => {
  await expectNative((effect, handler) => solid.createEffect(effect, handler), "runner-value");
});

test("createRenderEffect(fn) does not throw and runs the effect", async () => {
  await expectRunsOnce((effect) => solid.createRenderEffect(effect));
});

test("createRenderEffect(fn, initialValue) preserves previous-value semantics", async () => {
  await expectPrevious(
    (effect, initial) => solid.createRenderEffect(effect, initial),
    "initial-render",
    "render",
    ["initial-render", "render-0"],
  );
});

test("createRenderEffect(fn, nativeHandler) takes the native path", async () => {
  await expectNative((effect, handler) => solid.createRenderEffect(effect, handler), "render-value");
});

test("createComputed(fn) inherits the fixed createEffect path", async () => {
  await expectRunsOnce((effect) => solid.createComputed(effect));
});

test("onMount(fn) runs the callback once via the fixed path", async () => {
  await expectRunsOnce((effect) => solid.onMount(effect));
});

test("createResource(fetcher) updates loading, value, and error accessors", async () => {
  const payload = { id: "chapter-alpha" };
  let resolvePayload: (value: typeof payload) => void = () => {};
  await withRoot(
    () => {
      const [resource] = solid.createResource(
        () => new Promise<typeof payload>((resolve) => (resolvePayload = resolve)),
      );
      return resource;
    },
    async (resource) => {
      flush();
      expect(resource.loading()).toBe(true);
      expect(resource()).toBeUndefined();
      expect(resource.error()).toBeUndefined();
      resolvePayload(payload);
      await expect.poll(() => resource.loading()).toBe(false);
      expect(resource()).toEqual(payload);
      expect(resource.error()).toBeUndefined();
    },
  );
});

test("createResource(fetcher) sets error accessor on rejection", async () => {
  const failure = new Error("fetch failed");
  let rejectPayload: (reason: unknown) => void = () => {};
  await withRoot(
    () => {
      const [resource] = solid.createResource(
        () => new Promise<unknown>((_resolve, reject) => (rejectPayload = reject)),
      );
      return resource;
    },
    async (resource) => {
      flush();
      expect(resource.loading()).toBe(true);
      rejectPayload(failure);
      await expect.poll(() => resource.loading()).toBe(false);
      expect(resource()).toBeUndefined();
      expect(resource.error()).toBe(failure);
    },
  );
});

test("createSignal smoke: get and set", async () => {
  await withRoot(
    () => solid.createSignal("before"),
    ([value, setValue]) => {
      expect(value()).toBe("before");
      setValue("after");
      expect(value()).toBe("after");
    },
  );
});

test("For smoke: renders each item and Show smoke: renders when when-true", async () => {
  await withRoot(
    () => ({
      rendered: solid.For({
        each: ["alpha", "bravo"],
        children: (item) => item().toUpperCase(),
      }) as solid.Accessor<string[]>,
      shown: solid.Show({ when: true, fallback: "hidden", children: "visible" }),
    }),
    ({ rendered, shown }) => {
      flush();
      expect(rendered()).toEqual(["ALPHA", "BRAVO"]);
      expect(shown()).toBe("visible");
    },
  );
});
