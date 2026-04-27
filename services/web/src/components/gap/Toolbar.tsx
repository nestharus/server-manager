import { createSignal, For } from "solid-js";

import styles from "./gap.module.css";

export interface ToolbarAction {
  readonly id: string;
  readonly label: string;
  readonly onPress: () => void;
}

export function Toolbar(props: {
  readonly label: string;
  readonly actions: readonly ToolbarAction[];
}) {
  let toolbarRef: HTMLDivElement | undefined;
  const [activeIndex, setActiveIndex] = createSignal(0);

  const focusButton = (index: number) => {
    setActiveIndex(index);
    const button = toolbarRef?.querySelectorAll<HTMLButtonElement>("[role=button]").item(index);
    button?.focus();
  };

  const onKeyDown = (event: KeyboardEvent) => {
    const last = props.actions.length - 1;
    if (event.key === "ArrowRight") {
      event.preventDefault();
      focusButton(activeIndex() === last ? 0 : activeIndex() + 1);
    }
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      focusButton(activeIndex() === 0 ? last : activeIndex() - 1);
    }
    if (event.key === "Home") {
      event.preventDefault();
      focusButton(0);
    }
    if (event.key === "End") {
      event.preventDefault();
      focusButton(last);
    }
  };

  return (
    <div
      ref={toolbarRef}
      role="toolbar"
      aria-label={props.label}
      class={styles.toolbar}
      onKeyDown={onKeyDown}
    >
      <For each={props.actions}>
        {(action, index) => (
          <button
            role="button"
            type="button"
            tabindex={activeIndex() === index() ? 0 : -1}
            onClick={action().onPress}
          >
            {action().label}
          </button>
        )}
      </For>
    </div>
  );
}
