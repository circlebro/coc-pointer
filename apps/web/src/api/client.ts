import type { components, paths } from "./schema";

export type Member = components["schemas"]["Member"];
export type MemberInclude = components["schemas"]["MemberInclude"];
export type MemberListResponse = components["schemas"]["MemberListResponse"];

// profile 을 부른 응답. 부르지 않으면 키가 아예 없고, 불렀는데 null 이면 지금
// CoC 에서 볼 수 없다는 뜻이다(클랜을 나갔거나 계정이 사라졌다).
export type MemberWithProfile = Member & {
  profile: Member["profile"] | null;
};
export type Clan = components["schemas"]["Clan"];
export type ClanListResponse = components["schemas"]["ClanListResponse"];

const BASE_URL = "https://coc-api.coc-api.workers.dev";

// satisfies 로 적어 두면 스펙에 없는 주소를 부를 때 빌드가 걸린다. 그냥
// 문자열로 두면 스펙에서 주소를 바꾸고 타입을 다시 생성해도 여기는 따라오지
// 않고, 화면이 띄워진 뒤에야 404 로 드러난다.
const MEMBERS = "/api/v1/public/members" satisfies keyof paths;
const CLANS = "/api/v1/public/clans" satisfies keyof paths;

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`서버가 ${response.status} 로 답했습니다`);
  }
  return response.json();
}

// 기본 응답은 우리 DB 값만 담는다. 이름·직책·홀·트로피는 우리 DB 에 없으며
// include=profile 로 청할 때 서버가 CoC 에 묻는다.
export async function fetchMembers(
  includes: MemberInclude[] = [],
): Promise<MemberListResponse> {
  const query = includes.length > 0 ? `?include=${includes.join(",")}` : "";
  return get<MemberListResponse>(`${MEMBERS}${query}`);
}

export async function fetchClans(): Promise<ClanListResponse> {
  return get<ClanListResponse>(CLANS);
}

export type MemberSyncResult = components["schemas"]["MemberSyncResult"];

const MEMBERS_SYNC = "/api/v1/admin/members:sync" satisfies keyof paths;

/** 비밀번호가 맞지 않을 때. 화면이 다른 실패와 갈라 다루려고 따로 둔다. */
export class UnauthorizedError extends Error {
  constructor() {
    super("비밀번호가 맞지 않습니다");
    this.name = "UnauthorizedError";
  }
}

/** 클랜 명단을 지금 맞춘다. 운영 표면이라 비밀번호가 필요하다.
 *
 * 비밀번호는 어디에도 저장하지 않는다. 부르는 쪽이 들고 있다가 넘기고, 화면을
 * 새로 고치면 사라진다. 임시 조치이며 제대로 된 로그인이 오면 갈아 끼운다.
 */
export async function syncMembers(password: string): Promise<MemberSyncResult> {
  // HTTP 헤더는 ASCII 만 담는다. 한글이 섞이면 fetch 가 그 자리에서 터지는데,
  // 그 오류 문구로는 무엇이 잘못됐는지 알 수 없다.
  if (!/^[\x20-\x7E]+$/.test(password)) {
    throw new Error("비밀번호에는 영문·숫자·기호만 쓸 수 있습니다");
  }
  const response = await fetch(`${BASE_URL}${MEMBERS_SYNC}`, {
    method: "POST",
    headers: { "X-Admin-Password": password },
  });
  if (response.status === 401) {
    throw new UnauthorizedError();
  }
  if (!response.ok) {
    throw new Error(`서버가 ${response.status} 로 답했습니다`);
  }
  return response.json();
}
