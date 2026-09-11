import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Members } from "./pages/Members";

const root = document.getElementById("root");
if (root === null) {
  throw new Error("#root 를 찾지 못했습니다");
}

createRoot(root).render(
  <StrictMode>
    <h1>클랜원</h1>
    <Members />
  </StrictMode>,
);
