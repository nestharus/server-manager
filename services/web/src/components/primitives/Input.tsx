import type { JSX } from "solid-js";

import styles from "./controls.module.css";

export function Input(props: JSX.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} class={`${styles.input} ${props.class ?? ""}`} />;
}
