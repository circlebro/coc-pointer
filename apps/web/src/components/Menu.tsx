/** 화면 여섯 가운데 누구나 보는 셋.
 *
 * 순서와 이름은 docs/superpowers/specs/2026-09-14-scope-decisions.md 5번이
 * 정한 그대로다. 바꾸려면 그 문서를 먼저 고친다.
 *
 * 지금 만든 것은 클랜원 인원뿐이라 나머지는 누르면 알림만 띄운다. 메뉴에서
 * 아예 빼 두면 무엇이 만들어지는 중인지 아무도 모르고, 눌러도 아무 일이 없으면
 * 고장으로 보인다.
 */
const PAGES = ["클랜원 인원", "월별 점수", "리그전 명단"] as const;

export type Page = (typeof PAGES)[number];

export function Menu({
  current,
  onUnavailable,
}: {
  current: Page;
  onUnavailable: (name: string) => void;
}) {
  return (
    <nav className="menu">
      {PAGES.map((page) => (
        <button
          key={page}
          type="button"
          className={page === current ? "on" : undefined}
          aria-current={page === current ? "page" : undefined}
          onClick={page === current ? undefined : () => onUnavailable(page)}
        >
          {page}
        </button>
      ))}
      <button type="button" className="adm" onClick={() => onUnavailable("운영진")}>
        운영진
      </button>
    </nav>
  );
}
