import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Menu } from "./components/Menu";
import { Toast, useToast } from "./components/Toast";
import { ClanTitle } from "./pages/ClanTitle";
import { Members } from "./pages/Members";
import "./styles.css";

function App() {
  const { message, show } = useToast();

  return (
    <div className="page">
      <ClanTitle page="클랜원 인원" />
      <Menu current="클랜원 인원" onUnavailable={(name) => show(`${name} 화면은 준비 중입니다`)} />
      <Members />
      <Toast message={message} />
    </div>
  );
}

const root = document.getElementById("root");
if (root === null) {
  throw new Error("#root 를 찾지 못했습니다");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
