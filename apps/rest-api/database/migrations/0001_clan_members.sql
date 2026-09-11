-- coc-pointer D1 스키마
-- 설계: docs/superpowers/specs/2026-09-10-backend-server-design.md 4절
--
-- SQLite에는 참·거짓 타입이 없다. 0과 1을 담는 INTEGER 열로 두고
-- 파이썬에서 bool()로 바꿔 쓴다.

CREATE TABLE IF NOT EXISTS wars (
  id                 TEXT PRIMARY KEY,
  war_type           TEXT NOT NULL,
  start_time         TEXT NOT NULL,
  end_time           TEXT NOT NULL,
  team_size          INTEGER NOT NULL,
  attacks_per_member INTEGER NOT NULL,
  opponent_tag       TEXT NOT NULL,
  opponent_name      TEXT NOT NULL,
  in_progress        INTEGER NOT NULL DEFAULT 0,
  round_no           INTEGER,
  total_rounds       INTEGER
);

CREATE TABLE IF NOT EXISTS war_members (
  war_id   TEXT NOT NULL REFERENCES wars(id) ON DELETE CASCADE,
  tag      TEXT NOT NULL,
  name     TEXT NOT NULL,
  townhall INTEGER NOT NULL,
  PRIMARY KEY (war_id, tag)
);

CREATE TABLE IF NOT EXISTS attacks (
  war_id       TEXT NOT NULL,
  attacker_tag TEXT NOT NULL,
  attack_order INTEGER NOT NULL,
  stars        INTEGER NOT NULL,
  PRIMARY KEY (war_id, attacker_tag, attack_order),
  FOREIGN KEY (war_id, attacker_tag)
    REFERENCES war_members(war_id, tag) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS users (
  id            TEXT PRIMARY KEY,
  login_id      TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  display_name  TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'member',
  member_tag    TEXT,
  created_at    TEXT NOT NULL,
  last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monthly_scores (
  month       TEXT NOT NULL,
  tag         TEXT NOT NULL,
  name        TEXT NOT NULL,
  attacks     INTEGER NOT NULL,
  stars       INTEGER NOT NULL,
  score       REAL NOT NULL,
  computed_at TEXT NOT NULL,
  PRIMARY KEY (month, tag)
);

CREATE TABLE IF NOT EXISTS draws (
  month      TEXT PRIMARY KEY,
  winners    TEXT NOT NULL,
  candidates TEXT NOT NULL,
  slots      INTEGER NOT NULL,
  drawn_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_wars_end_time ON wars(end_time);
CREATE INDEX IF NOT EXISTS idx_monthly_scores_month ON monthly_scores(month);

-- 클랜원 표를 새로 만든다.
--
-- 앞선 설계의 members 표를 지우고 clan_members 로 바꾼다. 자료가 하나도
-- 없어 안전하다. 표 이름에 clan 이 들어가 war_members 와 나란히 읽히고,
-- role 컬럼이 users.role(서비스 권한)과 헷갈리지 않는다.

DROP TABLE IF EXISTS members;

-- role 과 status 에 값 목록을 못 박아 둔다. 표가 스스로를 지켜야 하기
-- 때문이다. 읽어 들이는 쪽은 이 문자열을 우리 자료형으로 바로 바꾸므로,
-- 목록에 없는 값이 한 행에라도 섞이면 그 한 행 때문에 조회가 통째로
-- 실패한다. SQLite 에는 제약만 나중에 덧붙이는 ALTER TABLE 이 없어, 처음
-- 지을 때 넣지 않으면 표를 다시 짓는 수밖에 없다.
CREATE TABLE clan_members (
  id                 TEXT PRIMARY KEY,
  tag                TEXT NOT NULL UNIQUE,
  name               TEXT NOT NULL,

  -- CoC API 가 채운다
  role               TEXT NOT NULL  -- ClanRole 과 함께 고친다
                     CHECK (role IN ('LEADER', 'COLEADER', 'ADMIN', 'MEMBER', 'UNKNOWN')),
  townhall           INTEGER,
  trophies           INTEGER,
  donations          INTEGER,
  donations_received INTEGER,

  -- 우리가 판정한다
  status             TEXT NOT NULL DEFAULT 'ACTIVE'  -- MemberStatus 와 함께 고친다
                     CHECK (status IN ('ACTIVE', 'INACTIVE')),
  created_at         TEXT NOT NULL,
  updated_at         TEXT NOT NULL,

  -- 관리자가 적는다. 동기화가 덮어쓰지 않는다
  description        TEXT
);

CREATE INDEX idx_clan_members_status ON clan_members(status);
