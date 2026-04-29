import { render } from "solid-js/web";

import { AppProviders } from "./app/providers";
import { router } from "./app/router";
import "./styles/layers.css";

const rootElement = document.querySelector<HTMLElement>("#root");
if (!rootElement) throw new Error("missing #root");
render(() => <AppProviders router={router} />, rootElement);
