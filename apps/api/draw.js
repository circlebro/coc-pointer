// 리그전 보상 추첨 서버 (Cloudflare Workers)
//
// GitHub Pages는 미리 만들어 둔 파일만 내려 주므로, 브라우저에서 뽑은 결과를 남길 곳이 없다.
// 이 작은 서버가 그 자리를 대신한다. 관리자가 페이지에서 "추첨하기"를 누르면 여기서 뽑아
// Workers KV에 기록하고, 그 뒤로는 클랜원 누가 열어도 같은 결과를 받아 간다.
//
// 필요한 설정 (Cloudflare 대시보드에서 지정한다)
//   KV 바인딩  DRAWS           : 뽑은 결과를 달마다 저장한다
//   시크릿     ADMIN_PASSWORD  : 추첨과 다시 뽑기에 필요한 비밀번호
//   변수       ALLOWED_ORIGIN  : 페이지 주소 (예: https://circlebro.github.io)

const MONTH = /^\d{4}-\d{2}$/;

export default {
  async fetch(request, env) {
    const origin = env.ALLOWED_ORIGIN || "*";
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: cors(origin) });
    }

    const month = new URL(request.url).pathname.split("/").filter(Boolean).pop();
    if (!MONTH.test(month || "")) {
      return json({ error: "주소 끝에 2026-09 형태의 달이 필요합니다." }, 400, origin);
    }

    if (request.method === "GET") {
      // 클랜원 누구나 결과를 읽을 수 있다.
      return json((await env.DRAWS.get(month, "json")) || null, 200, origin);
    }

    if (request.method !== "POST") {
      return json({ error: "지원하지 않는 요청입니다." }, 405, origin);
    }

    const body = await request.json().catch(() => ({}));
    if (!env.ADMIN_PASSWORD || body.password !== env.ADMIN_PASSWORD) {
      return json({ error: "비밀번호가 맞지 않습니다." }, 403, origin);
    }

    const saved = await env.DRAWS.get(month, "json");
    if (saved && !body.redraw) {
      // 이미 뽑았다면 그대로 돌려준다. 실수로 두 번 눌러도 결과가 바뀌지 않는다.
      return json(saved, 200, origin);
    }

    const candidates = Array.isArray(body.candidates) ? body.candidates : [];
    const slots = Math.min(Number(body.slots) || 0, candidates.length);
    if (!candidates.length || !slots) {
      return json({ error: "후보 목록이나 뽑을 인원이 없습니다." }, 400, origin);
    }

    const record = {
      month,
      winners: sample(candidates, slots),
      candidates,
      drawnAt: new Date().toISOString(),
      redrawnFrom: saved ? saved.drawnAt : null,
    };
    await env.DRAWS.put(month, JSON.stringify(record));
    return json(record, 200, origin);
  },
};

// 브라우저의 Math.random 대신 암호학적 난수를 쓴다. 예측하거나 맞출 수 없다.
function randomBelow(max) {
  const buf = new Uint32Array(1);
  crypto.getRandomValues(buf);
  return buf[0] % max;
}

function sample(pool, count) {
  const bag = pool.slice();
  for (let i = bag.length - 1; i > 0; i--) {
    const j = randomBelow(i + 1);
    const swap = bag[i];
    bag[i] = bag[j];
    bag[j] = swap;
  }
  return bag.slice(0, count);
}

function cors(origin) {
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}

function json(data, status, origin) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...cors(origin) },
  });
}
