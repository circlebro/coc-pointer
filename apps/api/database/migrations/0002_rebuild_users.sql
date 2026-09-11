-- users 표를 다시 짓는다. 없어진 표를 가리키는 외래키를 떼어내기 위해서다.
--
-- 0001 이 members 표를 지웠는데, 이미 배포된 데이터베이스의 users 에는
-- member_tag TEXT REFERENCES members(tag) 가 남아 있다. 0001 의 users 는
-- CREATE TABLE IF NOT EXISTS 라서 이미 있는 표를 고치지 않기 때문이다.
-- 그 상태에서는 member_tag 가 NULL 이어도 users 에 아무 행도 넣을 수 없다.
-- SQLite 는 외래키가 가리키는 표가 없으면 삽입 자체를 거부한다.
--
-- SQLite 에는 제약만 떼어내는 ALTER TABLE 이 없어 표를 다시 짓는 수밖에 없다.
-- 아직 로그인 기능을 만들지 않아 users 에 행이 하나도 없으므로 자료를 옮길
-- 필요가 없다. 사용자 관리를 붙인 뒤였다면 임시 표로 옮기는 절차가 필요했다.
--
-- 새 데이터베이스에서도 같은 결과가 나온다. 0001 이 만든 표를 지우고 같은
-- 모양으로 다시 만들 뿐이다.
--
-- member_tag 에 외래키를 두지 않는 까닭은 이렇다. 클랜원은 clan_members 가
-- 태그가 아니라 우리 식별자(id)로 관리하고, 사용자 계정은 아직 클랜원과
-- 이어지지 않은 채로도 있을 수 있다. 어느 쪽을 가리킬지는 사용자 관리를
-- 만들 때(TASK-23) 정한다.

DROP TABLE IF EXISTS users;

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
