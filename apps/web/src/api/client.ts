import type { components } from "./schema";

export type Member = components["schemas"]["Member"];
export type MemberListResponse = components["schemas"]["MemberListResponse"];

const BASE_URL = "https://coc-api.coc-api.workers.dev";

export async function fetchMembers(): Promise<MemberListResponse> {
  const response = await fetch(`${BASE_URL}/api/v1/members`);
  if (!response.ok) {
    throw new Error(`서버가 ${response.status} 로 답했습니다`);
  }
  return response.json();
}
