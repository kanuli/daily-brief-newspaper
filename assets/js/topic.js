(() => {
  "use strict";
  const $=(s,r=document)=>r.querySelector(s);
  const esc=(v="")=>String(v).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");
  const dedupe=(a=[])=>[...new Set(a.filter(Boolean))];
  const DEFS=[
    ["world","世界","歐洲 · 北美洲 · 南美洲 · 非洲 · 大洋洲（亞洲另見亞洲版）"],
    ["asia","亞洲","東亞 · 東南亞 · 南亞 · 中亞 · 西亞／中東 · 全亞洲"],
    ["hong-kong","香港","社會 · 法庭 · 公共政策 · 民生 · 文化"],
    ["japan","日本","社會 · 法庭 · 政策 · 交通 · 教育 · 醫療 · 生活"],
    ["market-economy","📈 財經 / 全球市場","美國 · 歐洲 · 台灣 · 日本 · 香港 · 中國 · 全球"],
    ["ai-tech","AI / 科技","AI · 半導體 · 軟件 · 網安 · 消費科技"],
    ["science-new-tech","🧪 科學 / 新技術","科研 · 新技術"],
    ["cybersecurity","🔐 網絡安全","Cybersecurity"],
    ["software-apps","📱 軟件 / App / 消費科技","Software · Apps"],
    ["manga-anime","漫畫 / Anime","作品 · 產業 · 票房 · 聲優 · 出版"],
    ["manchester-united","Manchester United","Club · Squad · Transfers"],
    ["football","Football","Europe · UEFA · International · J-League · Hong Kong · Worldwide"],
    ["breaking-news","📰 突發新聞","Breaking"],
    ["worth-following","🔎 今日值得跟進","Follow-up"],
    ["upcoming-events","📅 Upcoming events / 明日焦點","Upcoming"]
  ];
  const META=new Map(DEFS.map(([slug,title,subtitle])=>[slug,{slug,title,subtitle}]));

  function oneSlug(v=""){
    const raw=String(v).trim(), lower=raw.toLowerCase();
    if(!raw)return"worth-following";
    if(raw.startsWith("世界")||lower==="world")return"world";
    if(raw.startsWith("亞洲")||lower==="asia")return"asia";
    if(raw.startsWith("香港")||lower==="hong-kong")return"hong-kong";
    if(raw.startsWith("日本")||lower==="japan")return"japan";
    if(raw.startsWith("📈")||raw.startsWith("財經")||lower==="market-economy")return"market-economy";
    if(raw.startsWith("AI / 科技")||raw.startsWith("AI／科技")||lower==="ai-tech")return"ai-tech";
    if(raw.startsWith("科學")||lower==="science-new-tech")return"science-new-tech";
    if(raw.startsWith("網絡安全")||raw.startsWith("網路安全")||lower==="cybersecurity")return"cybersecurity";
    if(raw.startsWith("軟件")||raw.startsWith("App")||lower==="software-apps")return"software-apps";
    if(raw.startsWith("漫畫")||raw.startsWith("Anime")||lower==="manga-anime")return"manga-anime";
    if(raw.startsWith("Manchester United")||lower==="manchester-united")return"manchester-united";
    if(raw.startsWith("Football")||lower==="football")return"football";
    if(lower==="breaking-news")return"breaking-news";
    if(lower==="upcoming-events")return"upcoming-events";
    return"worth-following";
  }
  function sectionSlugs(value="",explicit=[]){
    const out=[];
    (Array.isArray(explicit)?explicit:[]).forEach(s=>{const n=oneSlug(s);if(n!=="worth-following")out.push(n);});
    const raw=String(value||""),l=raw.toLowerCase(),add=(s,h)=>{if(h)out.push(s);};
    add("world",raw.includes("世界")||l.includes("world")); add("asia",raw.includes("亞洲")||l.includes("asia"));
    add("hong-kong",raw.includes("香港")||l.includes("hong kong")); add("japan",raw.includes("日本")||l.includes("japan"));
    add("market-economy",raw.includes("財經")||raw.includes("市場")||l.includes("finance")); add("ai-tech",raw.includes("AI")||raw.includes("科技")||l.includes("tech"));
    add("science-new-tech",raw.includes("科學")); add("cybersecurity",raw.includes("網絡安全")||raw.includes("網路安全")||l.includes("cyber"));
    add("software-apps",raw.includes("軟件")||raw.includes("App")||l.includes("software")); add("manga-anime",raw.includes("漫畫")||raw.includes("Anime")||l.includes("anime"));
    add("manchester-united",raw.includes("Manchester United")||l.includes("manchester united")); add("football",raw.includes("Football")||raw.includes("足球")||l.includes("football"));
    if(!out.length)out.push(oneSlug(raw)); return dedupe(out);
  }
  function ensureSection(data,slug){let s=data.sections.find(x=>x.slug===slug);if(!s){s={...(META.get(slug)||{slug,title:slug,subtitle:""}),articleIds:[]};data.sections.push(s);}return s;}
  function ensureSections(data){data=data||{};data.articles=Array.isArray(data.articles)?data.articles:[];const ok=Array.isArray(data.sections)&&data.sections.every(s=>s&&typeof s==="object"&&!Array.isArray(s));if(ok&&data.sections.length){data.sections=data.sections.map(s=>({...s,articleIds:dedupe(s.articleIds||[])}));return data;}const g=new Map();data.articles.forEach(a=>{if(!a?.id)return;const s=oneSlug(a.section);if(!g.has(s))g.set(s,[]);g.get(s).push(a.id);});data.sections=DEFS.filter(([s])=>g.has(s)).map(([slug,title,subtitle])=>({slug,title,subtitle,articleIds:dedupe(g.get(slug))}));return data;}

  function titleKey(v=""){return String(v).normalize("NFKC").toLowerCase().replace(/\d+(?:[.,]\d+)?/g,"").replace(/[\s\p{P}\p{S}]+/gu,"").replace(/(最新|正式|今日|今晚|新季|開季|至少|超過|逾)/g,"").slice(0,120);}
  function bigrams(v=""){const s=titleKey(v),set=new Set();for(let i=0;i<s.length-1;i++)set.add(s.slice(i,i+2));return set;}
  function similarity(a,b){const A=bigrams(a),B=bigrams(b);if(!A.size||!B.size)return 0;let hit=0;A.forEach(x=>{if(B.has(x))hit++;});return hit/(A.size+B.size-hit);}
  function sameEvent(a,b){if(!a||!b)return false;const ak=titleKey(a.title),bk=titleKey(b.title);if(ak&&bk&&(ak===bk||(ak.length>=16&&bk.length>=16&&(ak.includes(bk)||bk.includes(ak)))))return true;const sameUrl=a.sourceUrl&&b.sourceUrl&&String(a.sourceUrl).split("?")[0]===String(b.sourceUrl).split("?")[0];return !!(sameUrl&&similarity(a.title,b.title)>=0.12);}

  function mergeArticle(data,article,slugs=[],prepend=true){
    if(!article?.id)return;
    let i=data.articles.findIndex(x=>x.id===article.id);if(i<0)i=data.articles.findIndex(x=>sameEvent(x,article));
    let id=article.id;
    if(i>=0){const old=data.articles[i];id=old.id;const rollingOnly=article.isRolling&&!article.isLive;const published=!old.isRolling&&!old.isLive;data.articles[i]=rollingOnly&&published?{...article,...old,id}:{...old,...article,id};data.sections.forEach(s=>{if(article.id!==id)s.articleIds=(s.articleIds||[]).map(x=>x===article.id?id:x);s.articleIds=dedupe(s.articleIds||[]);});}else data.articles.push(article);
    slugs.forEach(slug=>{if(!META.has(slug))return;const s=ensureSection(data,slug);s.articleIds=prepend?dedupe([id,...(s.articleIds||[])]):dedupe([...(s.articleIds||[]),id]);});
  }
  const byId=(data,id)=>(data.articles||[]).find(a=>a.id===id);
  async function getJson(path,optional=false){const r=await fetch(path,{cache:"no-store"});if(optional&&r.status===404)return null;if(!r.ok)throw new Error(`${path} HTTP ${r.status}`);return r.json();}
  async function applyEditorialOverride(data){data=ensureSections(data);if(!data?.date)return data;const o=await getJson(`data/editorial-overrides/${data.date}.json`,true);if(!o)return data;(Array.isArray(o.articles)?o.articles:[]).forEach(a=>mergeArticle(data,a,sectionSlugs(a.section),false));Object.entries(o.sectionOverrides||{}).forEach(([slug,c])=>{const s=ensureSection(data,slug);if(c.title)s.title=c.title;if(c.subtitle)s.subtitle=c.subtitle;if(Array.isArray(c.articleIds))s.articleIds=dedupe(c.articleIds);});const f=dedupe(o.moveToMarketEconomy||[]);if(f.length){data.sections.forEach(s=>{if(s.slug!=="market-economy")s.articleIds=(s.articleIds||[]).filter(id=>!f.includes(id));});ensureSection(data,"market-economy").articleIds=dedupe([...(ensureSection(data,"market-economy").articleIds||[]),...f]);}return data;}
  async function applyTopicExtras(data){if(!data?.date)return data;const e=await getJson(`data/topic-more/${data.date}.json`,true);if(!e)return data;(Array.isArray(e.articles)?e.articles:[]).forEach(a=>mergeArticle(data,a,sectionSlugs(a.section),false));(Array.isArray(e.sections)?e.sections:[]).forEach(x=>{if(!x||typeof x!=="object"||Array.isArray(x))return;const slug=oneSlug(x.slug||x.section||x.title),s=ensureSection(data,slug);if(x.title)s.title=x.title;if(x.subtitle)s.subtitle=x.subtitle;s.articleIds=dedupe([...(s.articleIds||[]),...(x.articleIds||[])]);});return data;}
  const rolling=(s,status="LATEST")=>({...s,section:s.section||"Rolling Desk",dek:s.dek||s.lede||"",context:s.context||s.background||"",why:s.why||s.whyImportant||"",watchNext:s.watchNext||s.nextStep||"",status:s.status||status,isRolling:true});
  async function applyDeskLatest(data){const d=await getJson("data/desk-latest.json",true);if(!d)return data;Object.entries(d.desks||{}).forEach(([slug,stories])=>(Array.isArray(stories)?stories:[]).slice().reverse().forEach(st=>{const a=rolling(st);mergeArticle(data,a,sectionSlugs(a.section,a.deskSlugs||[slug]),true);}));return data;}
  async function applyLive(data){const l=await getJson("data/live.json",true);if(!l)return data;(Array.isArray(l.items)?l.items:[]).slice().reverse().forEach(st=>{const a=rolling(st,st.status||"UPDATED");a.isLive=true;mergeArticle(data,a,sectionSlugs(a.section,a.deskSlugs),true);});return data;}
  function sourceMarkup(a){const ss=Array.isArray(a.sources)&&a.sources.length?a.sources:(a.sourceUrl?[{name:a.sourceName||"原文",url:a.sourceUrl}]:[]);return ss.length?`<div class="topic-sources"><strong>核實來源：</strong> ${ss.map(s=>`<a class="source-link" href="${esc(s.url||"#")}" target="_blank" rel="noopener noreferrer">${esc(s.name||"原文")} ↗</a>`).join(" · ")}</div>`:"";}
  const detail=(label,v,cls)=>v?`<p class="${cls}"><strong>${label}</strong>${esc(v)}</p>`:"";
  function bodyMarkup(a){const ps=String(a?.body||"").split(/\n\s*\n/).map(p=>p.trim()).filter(Boolean);return ps.length?`<div class="topic-full-body">${ps.map(p=>`<p>${esc(p)}</p>`).join("")}</div>`:"";}
  function renderArticle(a,featured=false){const badge=a.isLive?`<span class="topic-live-badge">${esc(a.status||"LIVE")}</span>`:(a.isRolling?`<span class="topic-latest-badge">${esc(a.status||"LATEST")}</span>`:"");return `<article class="topic-story ${featured?"topic-feature":""} ${a.isLive?"topic-live-story":""}"><div class="tag">${badge}${esc(a.section||"NEWS")}</div><h2>${esc(a.title||"")}</h2>${a.dek?`<p class="topic-dek">${esc(a.dek)}</p>`:""}<div class="topic-article-body">${detail("最新：",a.summary,"topic-summary")}${bodyMarkup(a)}${detail("背景：",a.context||a.background,"topic-context")}${detail("為何重要：",a.why||a.whyImportant,"why-mini")}${detail("下一步：",a.watchNext||a.nextStep,"topic-next")}</div><div class="story-meta">${esc(a.timeLabel||"")} ${a.sourceName?`· ${esc(a.sourceName)}`:""}</div>${sourceMarkup(a)}</article>`;}
  function uniqueStories(data,s){const out=[];dedupe(s.articleIds||[]).map(id=>byId(data,id)).filter(Boolean).forEach(a=>{if(!out.some(x=>sameEvent(x,a)))out.push(a);});return out;}
  function renderTopic(data){const host=$("#topic-sections");if(!host)return;const wanted=new Set((document.body.dataset.topicSlugs||"").split(",").map(x=>x.trim()).filter(Boolean)),sections=(data.sections||[]).filter(s=>wanted.has(s.slug));$("#topic-date")?.replaceChildren(document.createTextNode(data.dateLabel||data.date||""));const n=sections.reduce((sum,s)=>sum+uniqueStories(data,s).length,0),count=$("#topic-count");if(count)count.textContent=`${n} stories · Daily + Rolling Desk + Live`;host.innerHTML=sections.map(s=>{const stories=uniqueStories(data,s);if(!stories.length)return"";return `<section class="topic-section" id="${esc(s.slug)}"><div class="section-heading"><h2>${esc(s.title)}</h2><span>${esc(s.subtitle||`${stories.length} 則`)}</span></div><div class="topic-story-grid">${stories.map((a,i)=>renderArticle(a,i===0)).join("")}</div></section>`;}).join("")||`<p class="notice">本版目前未有可核實內容。</p>`;}
  async function init(){try{let data=ensureSections(await getJson("data/latest.json"));data=await applyEditorialOverride(data);data=await applyTopicExtras(data);data=await applyDeskLatest(data);data=await applyLive(data);renderTopic(data);}catch(e){console.error(e);const h=$("#topic-sections");if(h)h.innerHTML=`<p class="notice">本版暫時未能載入。請返回頭版或稍後重試。</p>`;}}
  init();
})();