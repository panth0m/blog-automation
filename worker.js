const DISCLOSURE = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받을 수 있습니다.";
const H = { "content-type": "application/json; charset=utf-8" };
const json = (v, s = 200) => new Response(JSON.stringify(v), { status: s, headers: H });
const tokenFor = (a, e) => ({ main:e.THREADS_TOKEN_MAIN, b:e.THREADS_TOKEN_B, c:e.THREADS_TOKEN_C, buybyebuy7:e.THREADS_TOKEN_BUYBYEBUY7 })[a];
const admin = (r, e) => !!e.ADMIN_API_KEY && r.headers.get("x-admin-key") === e.ADMIN_API_KEY;
async function setup(db) {
  await db.prepare("CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, account TEXT NOT NULL, topic TEXT NOT NULL, keyword TEXT NOT NULL, post_text TEXT NOT NULL, scheduled_at TEXT, status TEXT NOT NULL DEFAULT 'draft', threads_post_id TEXT, error TEXT, created_at TEXT NOT NULL, published_at TEXT)").run();
}
async function hexHmac(secret, text) {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), {name:"HMAC", hash:"SHA-256"}, false, ["sign"]);
  const b = new Uint8Array(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(text)));
  return Array.from(b).map(x => x.toString(16).padStart(2,"0")).join("");
}
async function products(keyword, env) {
  if (!env.COUPANG_ACCESS_KEY || !env.COUPANG_SECRET_KEY) return [];
  const path = "/v2/providers/affiliate_open_api/apis/openapi/products/search";
  const query = new URLSearchParams({keyword, limit:"2"}).toString();
  const date = new Date().toISOString().replace(/[-:]/g,"").replace(/.d{3}/,"").slice(2);
  const signature = await hexHmac(env.COUPANG_SECRET_KEY, date + "GET" + path + query);
  const res = await fetch("https://api-gateway.coupang.com" + path + "?" + query, {headers:{Authorization:"CEA algorithm=HmacSHA256, access-key=" + env.COUPANG_ACCESS_KEY + ", signed-date=" + date + ", signature=" + signature}});
  if (!res.ok) throw new Error("Coupang API " + res.status);
  return ((await res.json()).data?.productData || []).filter(x => x.productUrl).slice(0,2);
}
async function postThreads(account, text, env) {
  const token = tokenFor(account, env);
  if (!token) throw new Error("Missing Threads token for " + account);
  const created = await fetch("https://graph.threads.net/v1.0/me/threads", {method:"POST", body:new URLSearchParams({media_type:"TEXT",text,access_token:token})});
  if (!created.ok) throw new Error("Threads container " + created.status + ": " + await created.text());
  const id = (await created.json()).id;
  const sent = await fetch("https://graph.threads.net/v1.0/me/threads_publish", {method:"POST", body:new URLSearchParams({creation_id:id,access_token:token})});
  if (!sent.ok) throw new Error("Threads publish " + sent.status + ": " + await sent.text());
  return (await sent.json()).id;
}
async function publishDue(env) {
  await setup(env.DB);
  const now = new Date().toISOString();
  const rows = (await env.DB.prepare("SELECT * FROM jobs WHERE status='approved' AND (scheduled_at IS NULL OR scheduled_at <= ?) ORDER BY id LIMIT 12").bind(now).all()).results || [];
  const results = [];
  for (const job of rows) {
    try {
      let text = job.post_text.trim();
      if (!text.includes(DISCLOSURE)) text += "

" + DISCLOSURE;
      const items = await products(job.keyword, env);
      if (items.length) text += "

추천 제품 보기
" + items.map(x => "- " + x.productName + ": " + x.productUrl).join("
");
      if (text.length > 500) throw new Error("Post exceeds 500 characters after disclosure and links");
      const id = await postThreads(job.account, text, env);
      await env.DB.prepare("UPDATE jobs SET status='published', threads_post_id=?, published_at=?, error=NULL WHERE id=?").bind(id, new Date().toISOString(), job.id).run();
      results.push({id:job.id,status:"published",post_id:id});
    } catch (err) {
      await env.DB.prepare("UPDATE jobs SET status='failed', error=? WHERE id=?").bind(String(err).slice(0,1200),job.id).run();
      results.push({id:job.id,status:"failed",error:String(err)});
    }
  }
  return results;
}
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/health") return json({ok:true,service:"blog-automation",media:"text/public-image-url only"});
    if (!url.pathname.startsWith("/admin/")) return json({error:"Not found"},404);
    if (!admin(request,env)) return json({error:"Unauthorized"},401);
    await setup(env.DB);
    if (request.method === "GET" && url.pathname === "/admin/jobs") return json({jobs:(await env.DB.prepare("SELECT * FROM jobs ORDER BY id DESC LIMIT 100").all()).results || []});
    if (request.method === "POST" && url.pathname === "/admin/jobs") {
      const b = await request.json();
      for (const k of ["account","topic","keyword","post_text"]) if (!b[k]) return json({error:"Missing " + k},400);
      if (!["main","b","c","buybyebuy7"].includes(b.account)) return json({error:"Unknown account"},400);
      const r = await env.DB.prepare("INSERT INTO jobs(account,topic,keyword,post_text,scheduled_at,status,created_at) VALUES(?,?,?,?,?,'draft',?)").bind(b.account,b.topic,b.keyword,b.post_text,b.scheduled_at || null,new Date().toISOString()).run();
      return json({id:r.meta.last_row_id,status:"draft"},201);
    }
    const m = url.pathname.match(/^/admin/jobs/(d+)/approve$/);
    if (request.method === "POST" && m) { await env.DB.prepare("UPDATE jobs SET status='approved', error=NULL WHERE id=? AND status='draft'").bind(m[1]).run(); return json({id:Number(m[1]),status:"approved"}); }
    if (request.method === "POST" && url.pathname === "/admin/publish-due") return json({results:await publishDue(env)});
    return json({error:"Not found"},404);
  },
  async scheduled(_,env,ctx) { ctx.waitUntil(publishDue(env)); }
};
