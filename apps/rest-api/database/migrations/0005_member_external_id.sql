-- clan_members.tag 를 external_id 로 바꾼다.
--
-- clans 는 external_id 라 부르는데 clan_members 만 tag 였다. 같은 뜻(CoC 세계의
-- 식별자)인데 이름이 갈려 있어, 쓰는 쪽이 어느 자료형인지에 따라 다른 이름을
-- 기억해야 했다.
--
-- external_id 를 고른 까닭은 "바깥 세계의 식별자"라는 뜻이 이름에 드러나기
-- 때문이다. tag 는 CoC 용어라 다른 외부 시스템이 생기면 맞지 않는다.
--
-- SQLite 는 3.25 부터 ALTER TABLE ... RENAME COLUMN 을 지원하고, D1 은 그보다
-- 새 판이다. 인덱스와 CHECK 는 자동으로 따라오지만 이름은 따라오지 않으므로
-- UNIQUE 인덱스만 다시 만든다.

ALTER TABLE clan_members RENAME COLUMN tag TO external_id;
