import { Dialog } from "@ark-ui/solid";
import type { ParentProps } from "solid-js";

import styles from "./ark.module.css";
import { Button } from "./Button";

export function ArkDialog(
  props: ParentProps<{ readonly title: string; readonly trigger: string }>,
) {
  return (
    <Dialog.Root>
      <Dialog.Trigger class={styles.trigger}>{props.trigger}</Dialog.Trigger>
      <Dialog.Backdrop class={styles.backdrop} />
      <Dialog.Positioner class={styles.positioner}>
        <Dialog.Content class={styles.dialog}>
          <Dialog.Title class={styles.dialogTitle}>{props.title}</Dialog.Title>
          <div class={styles.dialogBody}>{props.children}</div>
          <Dialog.CloseTrigger>
            <Button type="button" variant="secondary">
              Close
            </Button>
          </Dialog.CloseTrigger>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}
