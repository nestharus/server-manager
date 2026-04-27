import { For, createMemo } from "solid-js";
import { Combobox, createListCollection } from "@ark-ui/solid";

import styles from "./ark.module.css";
import type { SelectOption } from "./ArkSelect";

export function ArkCombobox(props: {
  readonly label: string;
  readonly options: readonly SelectOption[];
}) {
  const collection = createMemo(() =>
    createListCollection({
      items: [...props.options],
      itemToString: (item) => item.label,
      itemToValue: (item) => item.value,
    }),
  );

  return (
    <Combobox.Root collection={collection()}>
      <Combobox.Label class={styles.label}>{props.label}</Combobox.Label>
      <Combobox.Control class={styles.control}>
        <Combobox.Input class={styles.input} />
        <Combobox.Trigger class={styles.iconTrigger}>v</Combobox.Trigger>
      </Combobox.Control>
      <Combobox.Positioner>
        <Combobox.Content class={styles.popover}>
          <Combobox.List>
            <For each={collection().items}>
              {(item) => (
                <Combobox.Item item={item()} class={styles.option}>
                  <Combobox.ItemText>{item().label}</Combobox.ItemText>
                </Combobox.Item>
              )}
            </For>
          </Combobox.List>
          <Combobox.Empty class={styles.empty}>No matches</Combobox.Empty>
        </Combobox.Content>
      </Combobox.Positioner>
    </Combobox.Root>
  );
}
