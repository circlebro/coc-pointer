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
  role               TEXT NOT NULL,
  townhall           INTEGER,
  trophies           INTEGER,
  donations          INTEGER,
  donations_received INTEGER,

  -- 우리가 판정한다
  status             TEXT NOT NULL DEFAULT 'ACTIVE',
  created_at         TEXT NOT NULL,
  updated_at         TEXT NOT NULL,

  -- 관리자가 적는다. 동기화가 덮어쓰지 않는다
  description        TEXT
);
CREATE INDEX idx_clan_members_status ON clan_members(status);
