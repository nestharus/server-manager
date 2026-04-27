import { QueryClient, QueryClientProvider } from "@tanstack/solid-query";
import { SolidQueryDevtools } from "@tanstack/solid-query-devtools";
import { RouterProvider } from "@tanstack/solid-router";
import { TanStackRouterDevtools } from "@tanstack/solid-router-devtools";
import type { ParentProps } from "solid-js";

import { useTheme } from "./store";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

function ThemeRuntime(props: ParentProps) {
  useTheme();

  return <>{props.children}</>;
}

export function AppProviders(props: { router: any }) {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeRuntime>
        <RouterProvider router={props.router} />
      </ThemeRuntime>
      {import.meta.env.DEV ? (
        <>
          <TanStackRouterDevtools router={props.router} position="bottom-right" />
          <SolidQueryDevtools initialIsOpen={false} />
        </>
      ) : null}
    </QueryClientProvider>
  );
}
