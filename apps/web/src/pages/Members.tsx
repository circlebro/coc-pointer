import { useEffect, useState } from "react";
import { fetchMembers, type Member } from "../api/client";
import { roleLabel, statusLabel } from "../labels";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; members: Member[] };

export function Members() {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = () => {
    setState({ kind: "loading" });
    fetchMembers()
      .then((body) => setState({ kind: "ready", members: body.members }))
      .catch((error: Error) => setState({ kind: "error", message: error.message }));
  };

  useEffect(load, []);

  if (state.kind === "loading") {
    return <p>불러오는 중입니다.</p>;
  }

  // 실패와 빈 목록을 갈라 보여준다. 같아 보이면 원인을 찾을 수 없다.
  if (state.kind === "error") {
    return (
      <div>
        <p>클랜원을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.</p>
        <p>{state.message}</p>
        <button onClick={load}>다시 시도</button>
      </div>
    );
  }

  if (state.members.length === 0) {
    return <p>클랜원 자료가 아직 없습니다.</p>;
  }

  return (
    <table>
      <thead>
        <tr>
          <th>닉네임</th>
          <th>태그</th>
          <th>직책</th>
          <th>상태</th>
          <th>홀</th>
          <th>트로피</th>
          <th>기부</th>
        </tr>
      </thead>
      <tbody>
        {state.members.map((member) => (
          <tr key={member.id}>
            <td>{member.name}</td>
            <td>{member.tag}</td>
            <td>{roleLabel(member.role)}</td>
            <td>{statusLabel(member.status)}</td>
            <td>{member.townhall ?? "-"}</td>
            <td>{member.trophies ?? "-"}</td>
            <td>{member.donations ?? "-"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
