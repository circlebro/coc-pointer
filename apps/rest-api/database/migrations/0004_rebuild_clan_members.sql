-- 클랜원 표에서 CoC 가 주인인 값을 걷어낸다.
--
-- clans 가 이미 지키는 규칙을 clan_members 에도 적용한다. 우리는 CoC 에 물을
-- 열쇠(external_id)와 우리가 만들어 낸 값만 들고, 현황은 물을 때마다 CoC 에
-- 묻는다. 사본을 들면 두 곳에서 관리하게 되고 언젠가 어긋난다.
--
--   빠지는 것   name, role, townhall, trophies, donations, donations_received
--   들어오는 것 display_name, warnings, synced_at
--   이름 바뀜   tag → external_id
--
-- 이름을 담지 않아도 되는 까닭은 과거 기록이 제 이름을 들고 있기 때문이다.
-- war_members.name 은 그 클랜전 시점의 이름이고 monthly_scores.name 은 그달의
-- 이름이다. 계정이 사라져도 그 화면들은 읽힌다. 아무 기록도 없는 사람이
-- 계정을 지웠다면 우리가 아는 것은 태그뿐이며, 없는 이름을 지어내지 않는다.
--
-- 등급은 담지 않는다. 그달 점수가 정하는 값이라 league 도메인이 맡는다.
--
-- SQLite 는 CHECK 에 걸린 열을 DROP COLUMN 으로 뗄 수 없다. role 에 CHECK 가
-- 걸려 있으므로 표를 다시 짓는다. users 를 다시 지은 0002 와 같은 방식이다.

CREATE TABLE clan_members_new (
  id            TEXT PRIMARY KEY,

  -- CoC 에 물을 열쇠. 게임에서 이름을 바꿔도 이 값은 바뀌지 않는다
  external_id   TEXT NOT NULL UNIQUE,

  -- 사람이 정한 표기. 아무도 고치지 않았으면 NULL 이다.
  -- 동기화가 채우지 않는다. 채우면 사람이 정한 것인지 동기화가 써 넣은
  -- 것인지 나중에 구분할 수 없다. 비었을 때 무엇을 보여줄지는 화면이 정한다
  display_name  TEXT,

  -- 우리가 판정한다. CoC 는 "나갔다"를 알려주지 않으므로 명단에서 사라진 것을
  -- 보고 우리가 내린다
  status        TEXT NOT NULL DEFAULT 'ACTIVE'  -- MemberStatus 와 함께 고친다
                CHECK (status IN ('ACTIVE', 'INACTIVE')),

  -- 사람이 적는다. 동기화가 덮어쓰지 않는다
  warnings      INTEGER NOT NULL DEFAULT 0,
  description   TEXT,

  created_at    TEXT NOT NULL,

  -- updated_at 은 이 행이 마지막으로 바뀐 시각이라 메모를 고쳐도 올라가고,
  -- synced_at 은 CoC 명단에서 마지막으로 본 시각이라 동기화만 올린다
  updated_at    TEXT NOT NULL,
  synced_at     TEXT
);

INSERT INTO clan_members_new (
  id, external_id, display_name, status, warnings, description,
  created_at, updated_at, synced_at
)
SELECT
  id, tag, NULL, status, 0, description,
  created_at, updated_at, updated_at
FROM clan_members;

DROP TABLE clan_members;

ALTER TABLE clan_members_new RENAME TO clan_members;

CREATE INDEX idx_clan_members_status ON clan_members(status);
