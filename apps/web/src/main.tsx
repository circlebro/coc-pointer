import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ClanTitle } from "./pages/ClanTitle";
import { Members } from "./pages/Members";

const root = document.getElementById("root");
if (root === null) {
  throw new Error("#root 를 찾지 못했습니다");
}

createRoot(root).render(
  <StrictMode>
    <ClanTitle page="클랜원" />
    <Members />
  </StrictMode>,
);
