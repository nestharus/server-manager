import { For, createMemo } from "solid-js";
import { Select, createListCollection } from "@ark-ui/solid";

import styles from "./ark.module.css";

export interface SelectOption {
  readonly label: string;
  readonly value: string;
}

export function ArkSelect(props: {
  readonly label: string;
  readonly options: readonly SelectOption[];
  readonly value?: string;
  readonly onChange?: (value: string) => void;
}) {
  const collection = createMemo(() =>
    createListCollection({
      items: [...props.options],
      itemToString: (item) => item.label,
      itemToValue: (item) => item.value,
    }),
  );

  return (
    <Select.Root
      collection={collection()}
      value={props.value ? [props.value] : []}
      onValueChange={(details) => props.onChange?.(details.value[0] ?? "")}
    >
      <Select.Label class={styles.label}>{props.label}</Select.Label>
      <Select.Control class={styles.control}>
        <Select.Trigger class={styles.trigger}>
          <Select.ValueText placeholder="Select" />
          <Select.Indicator>▾</Select.Indicator>
        </Select.Trigger>
      </Select.Control>
      <Select.Positioner>
        <Select.Content class={styles.popover}>
          <Select.List>
            <For each={collection().items}>
              {(item) => (
                <Select.Item item={item()} class={styles.option}>
                  <Select.ItemText>{item().label}</Select.ItemText>
                  <Select.ItemIndicator>✓</Select.ItemIndicator>
                </Select.Item>
              )}
            </For>
          </Select.List>
        </Select.Content>
      </Select.Positioner>
      <Select.HiddenSelect />
    </Select.Root>
  );
}
