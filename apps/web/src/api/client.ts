import type { components, paths } from "./schema";

export type Member = components["schemas"]["Member"];
export type MemberInclude = components["schemas"]["MemberInclude"];
export type MemberListResponse = components["schemas"]["MemberListResponse"];

// profile 을 부른 응답. 부르지 않으면 키가 아예 없으므로, 화면이 이름이나 직책을
// 쓰려면 이 자료형으로 받아야 한다.
export type MemberWithProfile = Member & {
  profile: NonNullable<Member["profile"]>;
};
export type Clan = components["schemas"]["Clan"];
export type ClanListResponse = components["schemas"]["ClanListResponse"];

const BASE_URL = "https://coc-api.coc-api.workers.dev";

// satisfies 로 적어 두면 스펙에 없는 주소를 부를 때 빌드가 걸린다. 그냥
// 문자열로 두면 스펙에서 주소를 바꾸고 타입을 다시 생성해도 여기는 따라오지
// 않고, 화면이 띄워진 뒤에야 404 로 드러난다.
const MEMBERS = "/api/v1/members" satisfies keyof paths;
const CLANS = "/api/v1/clans" satisfies keyof paths;

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`서버가 ${response.status} 로 답했습니다`);
  }
  return response.json();
}

// 기본 응답은 우리 DB 값만 담는다. 이름·직책·홀·트로피는 CoC 가 주인이라
// include=profile 로 따로 청해야 실려 온다.
export async function fetchMembers(
  includes: MemberInclude[] = [],
): Promise<MemberListResponse> {
  const query = includes.length > 0 ? `?include=${includes.join(",")}` : "";
  return get<MemberListResponse>(`${MEMBERS}${query}`);
}

export async function fetchClans(): Promise<ClanListResponse> {
  return get<ClanListResponse>(CLANS);
}
