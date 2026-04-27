import { Store } from "@tanstack/store";
import { useStore } from "@tanstack/solid-store";

export type ThemeName = "light" | "dark";

export interface UiState {
  readonly theme: ThemeName;
  readonly navigationCollapsed: boolean;
}

export const uiStore = new Store<UiState>({
  theme: "light",
  navigationCollapsed: false,
});

export function setTheme(theme: ThemeName) {
  uiStore.setState((state) => ({ ...state, theme }));
  document.documentElement.dataset.theme = theme;
}

export function setNavigationCollapsed(navigationCollapsed: boolean) {
  uiStore.setState((state) => ({ ...state, navigationCollapsed }));
}

export function useTheme() {
  const theme = useStore(uiStore, (state) => state.theme);
  return [theme, setTheme] as const;
}
