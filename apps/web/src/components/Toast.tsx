import { useCallback, useEffect, useRef, useState } from "react";

const HOLD_MS = 2400;

/** 짧게 떴다가 사라지는 알림.
 *
 * 브라우저 `alert()` 을 쓰지 않는다. 창이 떠 있는 동안 페이지가 통째로 멈추고,
 * 확인을 누르기 전에는 아무것도 못 한다. 알려 주기만 하면 되는 말에 그만한
 * 대가를 치를 이유가 없다.
 */
export function useToast() {
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);

  const show = useCallback((text: string) => {
    // 이미 떠 있으면 시계를 다시 잰다. 그러지 않으면 두 번째 알림이 첫 번째의
    // 남은 시간만큼만 보인다.
    window.clearTimeout(timer.current);
    setMessage(text);
    timer.current = window.setTimeout(() => setMessage(null), HOLD_MS);
  }, []);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  return { message, show };
}

/** 화면 아래에 뜨는 알림.
 *
 * `role="status"` 로 두면 화면 낭독기가 읽던 것을 끊지 않고 이어서 알린다.
 * 급한 일이 아니므로 `alert` 역할은 쓰지 않는다.
 */
export function Toast({ message }: { message: string | null }) {
  if (message === null) {
    return null;
  }
  return (
    <div className="toast" role="status" aria-live="polite">
      {message}
    </div>
  );
}
