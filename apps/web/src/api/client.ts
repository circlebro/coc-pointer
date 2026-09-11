import type { components, paths } from "./schema";

export type Member = components["schemas"]["Member"];
export type MemberListResponse = components["schemas"]["MemberListResponse"];

const BASE_URL = "https://coc-api.coc-api.workers.dev";

// satisfies 로 적어 두면 계약에 없는 주소를 부를 때 빌드가 걸린다. 그냥
// 문자열로 두면 계약에서 주소를 바꾸고 타입을 다시 생성해도 여기는 따라오지
// 않고, 화면이 띄워진 뒤에야 404 로 드러난다.
const MEMBERS = "/api/v1/members" satisfies keyof paths;

export async function fetchMembers(): Promise<MemberListResponse> {
  const response = await fetch(`${BASE_URL}${MEMBERS}`);
  if (!response.ok) {
    throw new Error(`서버가 ${response.status} 로 답했습니다`);
  }
  return response.json();
}
