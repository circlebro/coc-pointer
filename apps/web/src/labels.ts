import type { components } from "./api/schema";

type ClanRole = components["schemas"]["ClanRole"];
type MemberStatus = components["schemas"]["MemberStatus"];

// Record 로 적어 두면 서버가 값을 늘렸을 때 여기 빠진 것이 빌드에서 걸린다.
// 그것이 없으면 화면에 "VETERAN" 같은 코드가 그대로 나와 버그처럼 보인다.
const ROLE_LABEL: Record<ClanRole, string> = {
  LEADER: "대표",
  COLEADER: "공동 대표",
  ADMIN: "장로",
  MEMBER: "멤버",
  UNKNOWN: "알 수 없음",
};

const STATUS_LABEL: Record<MemberStatus, string> = {
  ACTIVE: "재적",
  INACTIVE: "탈퇴",
};

// 타입이 잡지 못하는 경우가 있다. 서버가 프론트보다 먼저 배포된 순간이 그렇다.
export const roleLabel = (role: string): string =>
  ROLE_LABEL[role as ClanRole] ?? "알 수 없음";

export const statusLabel = (status: string): string =>
  STATUS_LABEL[status as MemberStatus] ?? "알 수 없음";
