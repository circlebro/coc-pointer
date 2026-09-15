import { useEffect, useState } from "react";
import { fetchMembers, type MemberWithProfile } from "../api/client";
import { roleLabel, statusLabel } from "../labels";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; members: MemberWithProfile[] };

/** 사람이 정한 표기가 없으면 CoC 이름으로, 그것도 없으면 태그로 대신한다.
 *
 * 서버는 "사람이 정한 표기가 없다"는 사실만 내보낸다. 무엇을 대신 보여줄지는
 * 화면이 정한다. CoC 이름이 없는 경우는 클랜을 나갔거나 계정이 사라진 때다.
 */
function nameOf(member: MemberWithProfile): string {
  return member.displayName ?? member.profile?.name ?? member.externalId;
}

export function Members() {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = () => {
    setState({ kind: "loading" });
    // 직책·홀·트로피·기부는 우리 DB 에 없다. include=profile 로 청하면 서버가
    // CoC 를 한 번 부른다.
    fetchMembers(["profile"])
      .then((body) =>
        setState({ kind: "ready", members: body.members as MemberWithProfile[] }),
      )
      .catch((error: Error) => setState({ kind: "error", message: error.message }));
  };

  useEffect(load, []);

  return (
    <section className="win">
      <div className="bar">
        <h2>클랜원</h2>
        {state.kind === "ready" && <span className="meta">{state.members.length}명</span>}
      </div>
      <Body state={state} onRetry={load} />
      <div className="foot">
        등급과 점수, 클랜전 기록은 <b>아직 없습니다</b> — 클랜전 자료를 들여온 뒤에
        붙습니다. 이름은 운영진이 따로 정한 표기가 있으면 그것을, 없으면 게임 안
        이름을 보여 줍니다.
      </div>
    </section>
  );
}

function Body({ state, onRetry }: { state: State; onRetry: () => void }) {
  if (state.kind === "loading") {
    return (
      <div className="state">
        <p>불러오는 중입니다.</p>
      </div>
    );
  }

  // 실패와 빈 목록을 갈라 보여준다. 같아 보이면 원인을 찾을 수 없다.
  if (state.kind === "error") {
    return (
      <div className="state">
        <p>클랜원을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.</p>
        <p>{state.message}</p>
        <button type="button" onClick={onRetry}>
          다시 시도
        </button>
      </div>
    );
  }

  if (state.members.length === 0) {
    return (
      <div className="state">
        <p>클랜원 자료가 아직 없습니다.</p>
      </div>
    );
  }

  return (
    <div className="scroll">
      <table>
        <thead>
          <tr>
            <th>순번</th>
            <th>홀</th>
            <th className="l">닉네임</th>
            <th className="l">태그</th>
            <th className="l">직책</th>
            <th className="l">상태</th>
            <th>트로피</th>
            <th>기부</th>
            <th>경고</th>
          </tr>
        </thead>
        <tbody>
          {state.members.map((member, index) => (
            <tr key={member.id} className={member.status === "ACTIVE" ? undefined : "dim"}>
              <td className="rk">{index + 1}</td>
              <td className="v">{member.profile?.townhall ?? "-"}</td>
              <td>{nameOf(member)}</td>
              <td className="tag">{member.externalId}</td>
              <td>{member.profile ? roleLabel(member.profile.role) : "-"}</td>
              <td>{statusLabel(member.status)}</td>
              <td className="v">{member.profile?.trophies ?? "-"}</td>
              <td className="v">{member.profile?.donations ?? "-"}</td>
              <td className="v">{member.warnings || ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
