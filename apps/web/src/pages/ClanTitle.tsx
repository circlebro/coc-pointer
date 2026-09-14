import { useEffect, useState } from "react";
import { fetchClans } from "../api/client";

export function ClanTitle({ page }: { page: string }) {
  const [clanName, setClanName] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fetchClans()
      .then((body) => {
        if (!alive) return;
        // 지금은 클랜이 하나뿐이다. 여럿이 되면 어느 것을 보여 줄지 정해야 한다.
        setClanName(body.clans[0]?.displayName ?? null);
      })
      // 이름 때문에 화면 전체를 실패로 만들지 않는다. 클랜원 목록은 그것대로
      // 자기 상태를 보여 준다.
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  // 클랜 이름과 페이지 이름을 둘 다 남긴다. 한 자리를 놓고 맞바꾸면 클랜
  // 이름을 얻는 대신 이 페이지가 무엇을 보여 주는지를 잃는다.
  //
  // 이름을 못 받아 왔을 때는 페이지 이름만 크게 띄운다. 빈 줄을 남기거나
  // "불러오는 중" 같은 것을 두면 화면이 깨진 것처럼 보인다.
  if (clanName === null) {
    return <h1>{page}</h1>;
  }

  return (
    <header>
      <h1>{clanName}</h1>
      <p>{page}</p>
    </header>
  );
}
