import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// GitHub Pages 의 /coc-pointer/members/ 아래에 놓인다. base 를 맞추지 않으면
// 자바스크립트와 CSS 주소가 어긋나 화면이 빈 채로 뜬다.
export default defineConfig({
  plugins: [react()],
  base: "/coc-pointer/members/",
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
