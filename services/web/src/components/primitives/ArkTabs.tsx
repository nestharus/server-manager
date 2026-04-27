import { Tabs } from "@ark-ui/solid";
import type { JSX } from "solid-js";

import styles from "./ark.module.css";

export function ArkTabs(props: { readonly left: JSX.Element; readonly right: JSX.Element }) {
  return (
    <Tabs.Root defaultValue="left" class={styles.tabs}>
      <Tabs.List class={styles.tabList}>
        <Tabs.Trigger value="left" class={styles.tabTrigger}>
          Overview
        </Tabs.Trigger>
        <Tabs.Trigger value="right" class={styles.tabTrigger}>
          Details
        </Tabs.Trigger>
        <Tabs.Indicator class={styles.tabIndicator} />
      </Tabs.List>
      <Tabs.Content value="left" class={styles.tabPanel}>
        {props.left}
      </Tabs.Content>
      <Tabs.Content value="right" class={styles.tabPanel}>
        {props.right}
      </Tabs.Content>
    </Tabs.Root>
  );
}
