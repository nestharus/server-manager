// @ts-nocheck
import * as web from "../../node_modules/@solidjs/web/dist/web.js";
import { For, createComponent } from "solid-js";

export * from "../../node_modules/@solidjs/web/dist/web.js";

export function Index<T>(props: {
  readonly each: readonly T[] | undefined | null;
  readonly children: (item: () => T, index: number) => unknown;
}) {
  return createComponent(For, {
    get each() {
      return props.each ?? [];
    },
    children: (item: T, index: () => number) => props.children(() => item, index()),
  });
}

export const isDev = web.isDev ?? false;
