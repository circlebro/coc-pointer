-- 이 파일은 마이그레이션에서 생성되었다. 손으로 고치지 마라.
-- 고치려면 apps/api/database/migrations/ 에 파일을 더하고
-- ./scripts/dump-schema.sh 를 돌린다.

CREATE TABLE wars (
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
CREATE TABLE war_members (
  war_id   TEXT NOT NULL REFERENCES wars(id) ON DELETE CASCADE,
  tag      TEXT NOT NULL,
  name     TEXT NOT NULL,
  townhall INTEGER NOT NULL,
  PRIMARY KEY (war_id, tag)
);
CREATE TABLE attacks (
  war_id       TEXT NOT NULL,
  attacker_tag TEXT NOT NULL,
  attack_order INTEGER NOT NULL,
  stars        INTEGER NOT NULL,
  PRIMARY KEY (war_id, attacker_tag, attack_order),
  FOREIGN KEY (war_id, attacker_tag)
    REFERENCES war_members(war_id, tag) ON DELETE CASCADE
);
CREATE TABLE settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE monthly_scores (
  month       TEXT NOT NULL,
  tag         TEXT NOT NULL,
  name        TEXT NOT NULL,
  attacks     INTEGER NOT NULL,
  stars       INTEGER NOT NULL,
  score       REAL NOT NULL,
  computed_at TEXT NOT NULL,
  PRIMARY KEY (month, tag)
);
CREATE TABLE draws (
  month      TEXT PRIMARY KEY,
  winners    TEXT NOT NULL,
  candidates TEXT NOT NULL,
  slots      INTEGER NOT NULL,
  drawn_at   TEXT NOT NULL
);
CREATE INDEX idx_wars_end_time ON wars(end_time);
CREATE INDEX idx_monthly_scores_month ON monthly_scores(month);
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
CREATE TABLE users (
  id            TEXT PRIMARY KEY,
  login_id      TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  display_name  TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'member',
  member_tag    TEXT,
  created_at    TEXT NOT NULL,
  last_login_at TEXT
);
CREATE TABLE clans (
  -- 우리 식별자. 주소에서 '#' 을 인코딩하지 않으려고 external_id 와 따로 둔다.
  id            TEXT PRIMARY KEY,

  -- CoC 클랜 태그. 이 값으로 CoC API 를 부른다. 클랜을 만들 때 정해지고
  -- 바뀌지 않으므로 동기화할 때 이것으로 찾는다.
  external_id   TEXT NOT NULL UNIQUE,

  -- 우리가 붙이는 이름. 첫 동기화 때 CoC 이름으로 채우고 그 뒤로는 우리가
  -- 관리한다. 게임에서 클랜 이름을 바꿔도 우리 표기는 그대로 둘 수 있다.
  display_name  TEXT,

  -- 우리가 이 클랜을 다루는가. CoC 는 이것을 모른다.
  -- 값 목록을 못 박는 까닭은 clan_members 와 같다. 읽어 들이는 쪽이 이
  -- 문자열을 우리 자료형으로 바로 바꾸므로, 목록에 없는 값이 한 행에라도
  -- 섞이면 조회가 통째로 실패한다. SQLite 는 제약을 나중에 못 붙인다.
  status        TEXT NOT NULL DEFAULT 'ACTIVE'  -- ClanStatus 와 함께 고친다
                CHECK (status IN ('ACTIVE', 'INACTIVE')),

  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);
CREATE INDEX idx_clans_status ON clans(status);
