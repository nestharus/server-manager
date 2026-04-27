import type { JSX } from "solid-js";

import styles from "./gap.module.css";

export function Meter(
  props: {
    readonly label: string;
    readonly value: number;
    readonly min?: number;
    readonly max?: number;
  } & JSX.HTMLAttributes<HTMLDivElement>,
) {
  const min = () => props.min ?? 0;
  const max = () => props.max ?? 100;

  return (
    <div {...props} class={`${styles.meterGroup} ${props.class ?? ""}`}>
      <div class={styles.meterLabel}>
        <span>{props.label}</span>
        <span>
          {props.value}/{max()}
        </span>
      </div>
      <meter class={styles.meter} min={min()} max={max()} value={props.value}>
        {props.value}
      </meter>
    </div>
  );
}
