import { useState } from "react";
import { syncMembers, UnauthorizedError } from "../api/client";

type State = "쉼" | "비밀번호" | "도는중";

/** 명단을 지금 맞추는 버튼.
 *
 * 운영 표면을 부르므로 비밀번호가 필요하다. 눌렀을 때 비밀번호 칸이 그 자리에
 * 열린다. 브라우저 `prompt()` 를 쓰지 않는다 — 떠 있는 동안 페이지가 통째로
 * 멈추고 모바일에서 특히 거슬린다.
 *
 * 비밀번호를 저장하지 않는다. 화면을 새로 고치면 사라진다. 임시 조치이며
 * 제대로 된 로그인이 오면 이 조각을 걷어낸다.
 */
export function SyncButton({
  onDone,
  onMessage,
}: {
  onDone: () => void;
  onMessage: (text: string) => void;
}) {
  const [state, setState] = useState<State>("쉼");
  const [password, setPassword] = useState("");

  const close = () => {
    setState("쉼");
    setPassword("");
  };

  const run = async () => {
    setState("도는중");
    try {
      const result = await syncMembers(password);
      // 무엇이 달라졌는지 말해 준다. "완료" 만으로는 돌긴 돈 건지 알 수 없다.
      const changed = [
        result.added > 0 ? `${result.added}명 들어옴` : null,
        result.left > 0 ? `${result.left}명 나감` : null,
      ].filter(Boolean);
      onMessage(
        changed.length > 0
          ? `명단을 맞췄습니다 — ${changed.join(", ")}`
          : `명단을 맞췄습니다 — 바뀐 사람 없음 (${result.total}명)`,
      );
      close();
      onDone();
    } catch (error) {
      if (error instanceof UnauthorizedError) {
        // 칸을 닫지 않는다. 오타였다면 다시 치면 된다
        onMessage(error.message);
        setState("비밀번호");
        return;
      }
      onMessage((error as Error).message);
      close();
    }
  };

  if (state === "쉼") {
    return (
      <button type="button" className="ghost" onClick={() => setState("비밀번호")}>
        명단 맞추기
      </button>
    );
  }

  return (
    <form
      className="sync"
      onSubmit={(event) => {
        event.preventDefault();
        void run();
      }}
    >
      <input
        type="password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        placeholder="운영 비밀번호"
        aria-label="운영 비밀번호"
        autoFocus
        disabled={state === "도는중"}
      />
      <button type="submit" disabled={state === "도는중" || password === ""}>
        {state === "도는중" ? "맞추는 중" : "맞추기"}
      </button>
      <button type="button" className="ghost" onClick={close} disabled={state === "도는중"}>
        취소
      </button>
    </form>
  );
}
