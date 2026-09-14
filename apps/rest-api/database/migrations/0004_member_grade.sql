-- 클랜원에게 등급을 매길 자리.
--
-- 시트에서는 클랜인원관리 탭 E열에 ● △ ◎ ✕ 로 적혀 있다. 넷 가운데 둘만
-- 여기 담는다.
--
--   담는 것    FIXED(확정 ●) · EXCLUDED(제외 ✕)  — 사람이 매긴다
--   담지 않는 것  경쟁 △ · 예비 ◎              — 그 달 점수 순위가 가른다
--
-- 예비를 담지 않는 까닭은 그것이 매달 바뀌는 계산 결과이기 때문이다. 30위
-- 안이면 경쟁, 밖이면 예비다. 저장해 두면 점수가 바뀔 때마다 맞춰 줘야 하고
-- 그러다 어긋난다.
--
-- SQLite 는 ALTER TABLE 로 열을 하나씩만 더할 수 있다. CHECK 는 이렇게 붙여도
-- 든다(표를 다시 짓지 않아도 된다).

ALTER TABLE clan_members
  ADD COLUMN grade TEXT NOT NULL DEFAULT 'COMPETING'
  CHECK (grade IN ('FIXED', 'COMPETING', 'EXCLUDED'));

-- 왜 그 등급인지. "길드장", "쉬는 계정", "부캐" 같은 메모.
-- description 과 마찬가지로 동기화가 덮어쓰지 않는다.
ALTER TABLE clan_members ADD COLUMN grade_reason TEXT;

-- 경고 횟수. 표시만 하고 점수에 영향을 주지 않는다. 시트에도 감점 규정이 없다.
ALTER TABLE clan_members ADD COLUMN warnings INTEGER NOT NULL DEFAULT 0;

-- 등급으로 추리는 일이 잦다. 선발할 때 확정을 먼저 뽑고 제외를 걸러낸다.
CREATE INDEX idx_clan_members_grade ON clan_members(grade);
