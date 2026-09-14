-- CoC 에서 받은 시각을 따로 적을 자리.
--
-- updated_at 으로는 이 질문에 답할 수 없다. 등급을 고치는 PATCH 도 그 값을
-- 올리기 때문이다. 등급만 바꾼 뒤에 "CoC 에서 방금 받은 값"이라고 내보내면
-- 거짓말이 된다.
--
--   updated_at  이 행이 마지막으로 바뀐 시각 (동기화든 수정이든)
--   synced_at   CoC 가 준 값을 마지막으로 받아 적은 시각 (동기화만)
--
-- 이미 담겨 있는 행은 updated_at 을 그대로 옮긴다. 수정 경로가 아직 없던 때라
-- 그 값이 곧 동기화 시각이기 때문이다. 앞으로는 갈라진다.
ALTER TABLE clan_members ADD COLUMN synced_at TEXT;

UPDATE clan_members SET synced_at = updated_at WHERE synced_at IS NULL;
