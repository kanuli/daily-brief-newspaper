#!/usr/bin/env python3
import json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=ROOT/'data'/'desk-latest.json'
d=json.loads(p.read_text(encoding='utf-8'))
stories=[
{
'id':'hk-school-start-transport-20260901-0800','desk':'hong-kong','status':'LATEST','deskSlugs':['hong-kong'],'section':'香港｜開學日／交通','sectionLabel':'香港','mediaLabel':'香港',
'title':'全港今日開學　運輸署升級聯合監察、籲學生預留更多交通時間','dek':'運輸署預計首個上課日道路較平日繁忙，鐵路、巴士、渡輪及跨境學生服務均已要求準備加班與後備運力。','summary':'9月1日新學年開始，運輸署聯同警方及主要公共交通營辦商加強監察交通，提醒學生提早熟習路線並預留更多出行時間。','body':'香港新學年今日開始。運輸署在8月31日再次提醒學生，首個上課日整體道路交通預料較平日繁忙，尤其新生應預先熟習往返學校的公共交通路線和班次，乘搭渡輪的學生亦要先確認船種及航程。當局同時呼籲駕駛者盡量避免駛入學校集中地區。\n\n主要鐵路、專營巴士、渡輪、的士及跨境學生交通服務已被要求準備足夠班次、後備車船與人手。運輸署緊急事故交通協調中心今早會提升至最高級別的聯合督導模式，並派員到主要轉車站、學校區、口岸及隧道現場監察，必要時安排加班或交通管理措施。','context':'9月1日是全港大部分學校新學年首個上課日，早上繁忙時段同時遇上熱帶氣旋沙德爾帶來的風雨，交通安排較一般開學日更需要即時監察。','why':'開學日交通直接影響大量學生、家長與通勤人士；風雨與額外學生客流疊加時，公共交通後備運力和道路管理尤其重要。','watchNext':'留意運輸署早上交通更新、港鐵及巴士加班安排、主要學校區和口岸車流，以及沙德爾風雨是否造成額外延誤。','sourceName':'香港運輸署／The Standard','sourceUrl':'https://www.info.gov.hk/gia/general/202608/31/P2026082800222.htm','timeLabel':'9月1日08:00 HKT前核實','sources':[{'name':'香港運輸署','url':'https://www.info.gov.hk/gia/general/202608/31/P2026082800222.htm'},{'name':'The Standard','url':'https://www.thestandard.com.hk/news/a'}],'image':None
},
{
'id':'hk-shein-ipo-debut-20260901-0800','desk':'hong-kong','status':'LATEST','deskSlugs':['hong-kong','market-economy'],'section':'香港｜新股／零售科技','sectionLabel':'香港','mediaLabel':'香港',
'title':'SHEIN今日香港上市　集資約136億港元、暗盤先跌逾一成','dek':'公司以每股48.56港元定價，估值約265億美元；HKEX同步推出期權、衍生權證資格及沽空安排。','summary':'SHEIN 9月1日在港交所掛牌，IPO集資約17.4億美元；上市前暗盤價格一度較招股價低逾10%，市場將檢驗投資者對其增長、關稅與監管風險的接受程度。','body':'網上快時尚集團SHEIN今日在香港交易所掛牌。Reuters報道，公司以每股48.56港元定價，發售所得約136億港元、折合17.4億美元，上市估值約265億美元。公開及國際配售均錄得超額認購，但上市前暗盤交易一度較招股價低逾一成，反映市場對增長放慢、關稅及監管風險仍有戒心。\n\n港交所已確認，SHEIN股份上市當日起納入可沽空指定證券，並推出每周及每月期權，合資格發行人亦可發行相關衍生權證。這令今次大型新股不只影響零售投資者，也會即日進入香港衍生工具及風險管理市場；首日成交、收市價與期權流動性將成為主要觀察指標。','context':'SHEIN過去曾嘗試在紐約及倫敦上市，其後轉向香港；公司估值較2022年私人市場高峰大幅下降，並持續面對美歐關稅、消費者保護及供應鏈監管。','why':'這是香港今年具代表性的大型消費科技IPO之一，對新股市場氣氛、港交所成交與香港作為中國企業國際融資平台的吸引力均有指標作用。','watchNext':'留意SHEIN首日開市及收市表現、成交額、期權與沽空活動，以及公司對關稅、監管和盈利前景的後續說明。','sourceName':'Reuters／HKEX','sourceUrl':'https://www.reuters.com/business/retail-consumer/shein-prices-hong-kong-ipo-midpoint-range-raises-174-billion-2026-08-31/','timeLabel':'9月1日08:00 HKT前核實','sources':[{'name':'Reuters','url':'https://www.reuters.com/business/retail-consumer/shein-prices-hong-kong-ipo-midpoint-range-raises-174-billion-2026-08-31/'},{'name':'HKEX','url':'https://www.hkex.com.hk/News/News-Release/2026/260828news?sc_lang=en'}],'image':None
},
{
'id':'hk-longsys-ipo-launch-20260831-1100','desk':'hong-kong','status':'LATEST','deskSlugs':['hong-kong','market-economy','ai-tech'],'section':'香港｜新股／半導體','sectionLabel':'香港','mediaLabel':'香港',
'title':'深圳江波龍啟動香港招股　最高集資約62.7億港元、近八成擬投研發','dek':'已在深圳上市的記憶體公司發售約2,610萬股H股，最高招股價240.60港元，預計9月8日掛牌。','summary':'深圳江波龍電子8月31日展開香港招股，目標最高集資約62.7億港元；公司計劃把大部分所得投入晶片設計及先進記憶體產品研發。','body':'深圳上市的記憶體及半導體公司江波龍電子8月31日啟動香港H股招股。Reuters報道，公司計劃發售約2,610萬股H股，最高招股價每股240.60港元，最多集資約62.7億港元；最終定價預計9月4日確定，股份目標在9月8日開始於港交所買賣。\n\n公司表示，約78.3%的集資淨額將用於加強自主研發與創新能力，包括晶片設計及先進記憶體產品。Lenovo Group及北京君正等成為基石投資者。今次招股延續今年中國科技公司來港融資的趨勢，也令香港新股市場在SHEIN上市同一周繼續維持高發行活動。','context':'香港今年新股集資活躍，AI、半導體、機械人及消費科技企業均增加上市安排；江波龍本身已在深圳交易，H股上市將增加其海外融資渠道。','why':'半導體公司大型H股發行同時涉及香港資本市場活躍度、中國記憶體產業融資及本地科技板塊供應，具本地市場與產業雙重意義。','watchNext':'留意9月4日最終定價、國際及香港公開發售認購、9月8日掛牌表現，以及集資後晶片研發與產能投資進度。','sourceName':'Reuters／Bamboo Works','sourceUrl':'https://www.chinadailyasia.com/hk/article/638744','timeLabel':'8月31日11:00 HKT前核實','sources':[{'name':'Reuters（China Daily Asia轉載）','url':'https://www.chinadailyasia.com/hk/article/638744'},{'name':'Bamboo Works','url':'https://thebambooworks.com/longsys-launches-800-million-hong-kong-ipo-as-profit-soars/'}],'image':None
}
]
rows=d['desks'].setdefault('hong-kong',[])
existing={x.get('id') for x in rows}
for s in stories:
    if s['id'] not in existing: rows.append(s)
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('HK recovery injected',len(stories))
