-- 우리가 다루는 클랜.
--
-- CoC 가 주인인 값(마크·레벨·점수·전적)은 담지 않는다. 우리가 사본을 들고
-- 있으면 두 곳에서 관리하게 되고, 동기화 사이에 화면이 낡은 값을 보여 준다.
-- 필요하면 external_id 로 CoC 에 물으면 언제나 지금 값을 준다.
--
-- clan_members 는 아직 반대로 하고 있다(이름·홀·트로피를 담는다). 그쪽은
-- 화면과 점수 계산이 이미 물려 있어 한꺼번에 바꾸기 어렵다. TASK-27 에서
-- 같은 기준으로 옮긴다.

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
