import { icon, type IconDefinition } from "@fortawesome/fontawesome-svg-core";
import type { JSX } from "solid-js";

const definitions = {
  "circle-half-stroke": {
    prefix: "fas",
    iconName: "circle-half-stroke",
    icon: [
      512,
      512,
      [],
      "f042",
      "M256 48a208 208 0 1 0 0 416V48zm0-48a256 256 0 1 1 0 512 256 256 0 0 1 0-512z",
    ],
  },
  "shield-check": {
    prefix: "fas",
    iconName: "shield-check",
    icon: [
      512,
      512,
      [],
      "f2f7",
      "M256 0 64 64v144c0 123 78 238 192 304 114-66 192-181 192-304V64L256 0zm104 184L232 312l-72-72 34-34 38 38 94-94 34 34z",
    ],
  },
} satisfies Record<string, IconDefinition>;

export type IconName = keyof typeof definitions;

export function Icon(
  props: {
    readonly name: IconName;
    readonly title: string;
  } & JSX.HTMLAttributes<HTMLSpanElement>,
) {
  const rendered = () =>
    icon(definitions[props.name as IconName], { title: props.title }).html.join("");

  return (
    <span
      {...props}
      class={`faIcon ${props.class ?? ""}`}
      aria-hidden={props["aria-hidden"] ?? undefined}
      innerHTML={rendered()}
    />
  );
}
