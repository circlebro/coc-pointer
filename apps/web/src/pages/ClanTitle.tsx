import { useEffect, useState } from "react";
import { fetchClans } from "../api/client";

// 서버가 답하기 전이나 답하지 못했을 때 쓸 이름. 제목이 빈 채로 있으면
// 화면이 깨진 것처럼 보이므로, 클랜 이름을 몰라도 무엇을 보는 화면인지는
// 알려 준다.
const FALLBACK = "클랜원";

export function ClanTitle() {
  const [name, setName] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fetchClans()
      .then((body) => {
        if (!alive) return;
        // 지금은 클랜이 하나뿐이다. 여럿이 되면 어느 것을 보여 줄지 정해야 한다.
        const first = body.clans[0];
        setName(first?.displayName ?? null);
      })
      // 제목 때문에 화면 전체를 실패로 만들지 않는다. 클랜원 목록은 그것대로
      // 자기 상태를 보여 준다.
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  return <h1>{name ?? FALLBACK}</h1>;
}
