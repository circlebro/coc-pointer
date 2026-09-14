-- 2026-09-10 에 Cloudflare D1 에 실제로 올라간 스키마다 (커밋 3508a40).
-- 마이그레이션 체계를 들이기 전이라 이 파일을 통째로 실행하는 방식이었고,
-- 그래서 배포된 데이터베이스에는 d1_migrations 장부가 없다.
--
-- 이것을 남겨 두는 까닭은 하나다. 마이그레이션을 빈 데이터베이스에만 걸어 보면
-- 이미 올라간 것 위에 걸었을 때 무엇이 깨지는지 알 수 없다. 실제로 0001 이
-- members 표를 지우면서, 그것을 외래키로 가리키던 users 표를 못 쓰게 만든 적이
-- 있다. 그 일을 test_migration_on_deployed.py 가 지킨다.

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

CREATE TABLE IF NOT EXISTS members (
  tag                TEXT PRIMARY KEY,
  name               TEXT NOT NULL,
  role               TEXT,
  townhall           INTEGER,
  trophies           INTEGER,
  donations          INTEGER,
  donations_received INTEGER,
  in_clan            INTEGER NOT NULL DEFAULT 1,
  first_seen_at      TEXT NOT NULL,
  last_seen_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
  id            TEXT PRIMARY KEY,
  login_id      TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  display_name  TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'member',
  member_tag    TEXT REFERENCES members(tag),
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
