import { Link, Outlet, createRootRoute, createRoute, createRouter } from "@tanstack/solid-router";

import { Breadcrumbs } from "@/components/gap/Breadcrumbs";
import { Icon } from "@/components/icons/Icon";
import { Button } from "@/components/primitives/Button";
import { useTheme } from "./store";
import { AdminChaptersRoute } from "@/features/admin/AdminChaptersRoute";
import { HomeRoute } from "@/features/public/HomeRoute";

function RootShell() {
  const [theme, setTheme] = useTheme();

  return (
    <div class="appShell">
      <header class="appHeader">
        <div class="brandBlock">
          <span class="brandMark">H</span>
          <div>
            <p class="eyebrow">Humility</p>
            <h1>Server Manager</h1>
          </div>
        </div>
        <nav class="topNav" aria-label="Primary">
          <Link to="/" activeProps={{ "aria-current": "page" }}>
            Public
          </Link>
          <Link to="/admin/chapters" activeProps={{ "aria-current": "page" }}>
            Admin
          </Link>
        </nav>
        <Button
          variant="ghost"
          type="button"
          title="Toggle color theme"
          onClick={() => setTheme(theme() === "light" ? "dark" : "light")}
        >
          <Icon name="circle-half-stroke" title="Theme" />
        </Button>
      </header>
      <Breadcrumbs />
      <main class="appMain">
        <Outlet />
      </main>
    </div>
  );
}

const rootRoute = createRootRoute({
  component: RootShell,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: HomeRoute,
  staticData: {
    breadcrumb: "Public",
  },
});

const adminChaptersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin/chapters",
  component: AdminChaptersRoute,
  staticData: {
    breadcrumb: "Admin chapters",
  },
});

const routeTree = rootRoute.addChildren([indexRoute, adminChaptersRoute]);

export const router = createRouter({
  routeTree,
  defaultPreload: "intent",
  scrollRestoration: true,
});

declare module "@tanstack/solid-router" {
  interface Register {
    router: typeof router;
  }
}
