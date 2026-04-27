import type { JSX } from "solid-js";

import styles from "./controls.module.css";

export function Button(
  props: JSX.ButtonHTMLAttributes<HTMLButtonElement> & {
    readonly variant?: "primary" | "secondary" | "ghost";
  },
) {
  const variant = () => props.variant ?? "primary";
  return <button {...props} class={`${styles.button} ${styles[variant()]} ${props.class ?? ""}`} />;
}
