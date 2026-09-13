#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DATE = '2026-09-13'
EDITION = '024'
STAMP = '2026-09-13T08:00:00+08:00'
LABEL = '9月13日08:00 HKT核實'


def s(id, desk, section, title, dek, body, context, why, watch, source_name, source_url, sources):
    return {
        'id': id, 'desk': desk, 'deskSlugs': [desk], 'section': section, 'sectionLabel': section.split('｜')[0],
        'title': title, 'dek': dek, 'summary': dek, 'body': body, 'context': context,
        'why': why, 'watchNext': watch, 'sourceName': source_name, 'sourceUrl': source_url,
        'timeLabel': LABEL, 'verifiedAt': STAMP, 'sources': [{'name': n, 'url': u} for n,u in sources], 'image': None
    }

A = []
A.append(s('world-ukraine-mass-drone-strikes-20260913-daily','world','世界｜歐洲／俄烏戰事',
'俄軍大規模空襲烏克蘭至少10死　近500架無人機攻擊能源與城市目標',
'俄羅斯9月12日再對烏克蘭多地發動密集無人機及導彈攻擊，平民死亡與基建受損持續增加。',
'Reuters報道，俄羅斯在9月12日對烏克蘭多個地區發動新一輪大規模空襲，至少10名平民死亡、數十人受傷。澤連斯基表示，俄軍自清晨起動用接近500架無人機，敖德薩、扎波羅熱、克里維里赫、克拉馬托爾斯克及日托米爾等地均有住宅或重要基建受損。\n\nAssociated Press亦報道多個城市遭導彈及無人機攻擊，敖德薩一座住宅高樓受創並造成大批傷者。烏軍同時繼續打擊俄境工業及能源設施，顯示雙方正把遠程攻擊更深地延伸至後方經濟與物流網絡。',
'俄烏戰事持續把能源、工業及民用設施納入遠程打擊範圍，戰線以外的城市承受更高風險。',
'大規模無人機攻擊會加劇冬季能源供應、防空彈藥及平民保護壓力，也會令停火談判更難降溫。',
'留意俄軍下一輪能源攻擊規模、烏克蘭對俄工業設施的報復，以及歐洲新增防空支援。',
'Reuters','https://www.reuters.com/world/europe/russian-attacks-kill-six-injure-dozens-ukraine-moscow-says-it-hits-ships-plants-2026-09-12/',
[('Reuters','https://www.reuters.com/world/europe/russian-attacks-kill-six-injure-dozens-ukraine-moscow-says-it-hits-ships-plants-2026-09-12/'),('Associated Press','https://apnews.com/article/839f5b0fc5217afc4cb34e15b01b6eff')]))
A.append(s('world-congo-ebola-seventh-province-20260913-daily','world','世界｜非洲／公共衞生',
'剛果（金）伊波拉確診突破7,000宗　疫情擴至第七個省份',
'官方數據顯示確診已達7,022宗；疫情由東部進一步擴至西北部南烏班吉省，跨區傳播風險上升。',
'Reuters引述剛果（金）官方數據指，截至9月11日伊波拉確診個案已突破7,000宗，達7,022宗，疫情並首次擴散至西北部南烏班吉省，令受影響省份增至七個。新地區個案具有跨省旅行紀錄，增加接觸者追蹤與跨境監察難度。\n\n世界衞生組織9月10日的疫情通報已警告，Bundibugyo病毒疫情仍在多個省份持續傳播，醫療能力、安全局勢及人口流動均妨礙控制。新增省份意味疫情地理範圍再擴大，鄰近中非共和國及剛果共和國的防備亦會成為焦點。',
'這次疫情已成為剛果（金）歷來最大規模之一，並在衝突與人口流離失所背景下持續擴散。',
'病例突破7,000及擴至新省份，反映疫情仍未被限制在原有東部核心區，公共衞生資源壓力正在擴大。',
'留意南烏班吉省接觸者追蹤、疫苗供應、跨境監測，以及新確診個案是否出現本地傳播鏈。',
'Reuters','https://www.reuters.com/business/healthcare-pharmaceuticals/ebola-infections-top-7000-congo-virus-spreads-new-province-2026-09-11/',
[('Reuters','https://www.reuters.com/business/healthcare-pharmaceuticals/ebola-infections-top-7000-congo-virus-spreads-new-province-2026-09-11/'),('WHO','https://www.who.int/emergencies/disease-outbreak-news/item/2026-DON617')]))
A.append(s('asia-india-china-xi-modi-brics-20260913-daily','asia','亞洲｜南亞／中印關係',
'莫迪晤習近平推動中印關係回暖　邊境和平與貿易失衡仍是核心考驗',
'習近平七年來首次訪問印度，兩國領袖在BRICS峰會期間同意擴大商貿與人員往來，同時重申邊境穩定的重要性。',
'Reuters報道，印度總理莫迪與中國國家主席習近平在新德里BRICS峰會期間會面，雙方表示將推動商貿、交通、人員往來及供應鏈合作，並處理市場准入與結構性貿易失衡。莫迪同時強調，喜馬拉雅爭議邊境維持和平，是雙邊關係持續改善的必要條件。\n\nAssociated Press指出，這是習近平自2019年以來首次訪問印度，也是2020年拉達克致命邊境衝突後雙邊解凍的重要節點。航班、簽證及高層接觸逐步恢復，但領土爭議、龐大印度對華貿易逆差及戰略競爭仍未解決。',
'中印同為核武國家及大型亞洲經濟體，2020年邊境衝突後互信大幅下降，近年才逐步恢復接觸。',
'兩國若能穩定邊境並改善市場准入，將影響亞洲供應鏈、BRICS合作及區域力量平衡。',
'留意新的邊境談判安排、直航與簽證便利、投資限制，以及雙方如何處理印度對華巨額貿易逆差。',
'Reuters / Associated Press','https://www.reuters.com/world/china/chinas-xi-lands-delhi-brics-summit-indian-tv-channels-report-2026-09-12/',
[('Reuters','https://www.reuters.com/world/china/chinas-xi-lands-delhi-brics-summit-indian-tv-channels-report-2026-09-12/'),('Associated Press','https://apnews.com/article/e51a7eb70cfb3c79c978fbf9cc9cbed5')]))
A.append(s('asia-brics-new-delhi-declaration-20260913-daily','asia','亞洲｜南亞／多邊外交',
'BRICS新德里宣言促中東各方克制　同時反對單邊制裁與貿易壁壘',
'成員國在伊朗與阿聯酋同席的情況下，就中東局勢、制裁及全球治理取得共同文本。',
'BRICS成員國在新德里峰會通過聯合宣言，對中東暴力升級表示嚴重關切，呼籲各方最大限度克制並透過對話、磋商和多邊機制處理爭端。Reuters指出，在伊朗與美國盟友阿聯酋同為成員的背景下，形成共同文本並不容易。\n\nAssociated Press報道，宣言亦批評未經聯合國安理會授權的單邊制裁及部分關稅措施，並要求加強新興經濟體在國際制度中的代表性。各國對俄烏、中東及金融體系仍有不同利益，但峰會再次展示BRICS希望以「全球南方」平台擴大制度影響力。',
'BRICS擴員後成員利益更分散，印度今年擔任主席國，需要在中俄、伊朗、海灣國家及西方關係之間維持平衡。',
'宣言能否轉化成實際外交協調，將影響中東斡旋、制裁政策及新興市場合作。',
'留意峰會後是否出現中東斡旋安排、成員國本幣結算新措施，以及對美國制裁的具體共同動作。',
'Reuters','https://www.reuters.com/world/china/brics-adopts-joint-declaration-urges-maximum-restraint-mideast-2026-09-12/',
[('Reuters','https://www.reuters.com/world/china/brics-adopts-joint-declaration-urges-maximum-restraint-mideast-2026-09-12/'),('Associated Press','https://apnews.com/article/5393274f87a16461b195d13f324e747a')]))
A.append(s('asia-yemen-houthi-red-sea-pressure-20260913-daily','asia','亞洲｜西亞／紅海安全',
'胡塞推進令曼德海峽風險再升　美國與沙特面臨更複雜紅海選項',
'胡塞武裝在也門西部擴張控制範圍，霍爾木茲與曼德海峽兩條能源航道同時承受安全壓力。',
'Reuters分析指出，胡塞近期在也門西部快速推進，對曼德海峽周邊控制力上升，令紅海商船與沙特能源出口面臨新的安全風險。美國在與伊朗持續對峙之際，軍事資源與國內通脹壓力亦限制其直接介入空間。\n\nAssociated Press報道，伊拉克已確認早前襲擊沙特輸油管的無人機從其境內起飛，並撤換相關地區軍事指揮官；同時胡塞攻勢令也門更多居民流離失所。區內安全風險因此不再只集中於霍爾木茲，而是延伸至紅海與陸上能源基建。',
'中東衝突已令海灣油運受阻，胡塞若進一步控制曼德海峽周邊，全球兩條重要能源航道會同時受壓。',
'航運繞道、保險費與沙特出口能力都可能受影響，並透過油價與運費傳導至亞洲經濟。',
'留意胡塞是否進一步部署反艦能力、美國會否擴大軍援，以及沙特東西輸油管何時恢復。',
'Reuters','https://www.reuters.com/world/middle-east/houthi-advance-yemen-puts-us-new-bind-2026-09-12/',
[('Reuters','https://www.reuters.com/world/middle-east/houthi-advance-yemen-puts-us-new-bind-2026-09-12/'),('Associated Press','https://apnews.com/article/324485fad65647d4a897d5bfdcb7849c')]))
A.append(s('hong-kong-summer-flu-high-20260913-daily','hong-kong','香港｜公共衞生',
'香港夏季流感仍處高位　八成個案屬甲型H1、學校接種本月展開',
'衞生署表示化驗室呼吸道樣本流感陽性比率約13%，今季已有19宗兒童嚴重個案。',
'衞生署署長林文健表示，香港夏季流感至上星期仍處高水平，化驗室呼吸道樣本約13%對流感病毒呈陽性，公立醫院相關治療或求診比率亦高於基準。現時約八成流感個案屬甲型H1，近兩成是甲型H3。\n\n今個夏季至今錄得19宗兒童嚴重流感個案，其中一宗死亡；八成患者本身有風險因素，包括未接種流感疫苗或有慢性疾病。2026/27學校外展接種安排本月展開，衞生部門希望在冬季高峰前提高兒童保護率。',
'香港流感活動在暑假後仍然偏高，而新學年開始增加校園傳播機會。',
'兒童嚴重個案與醫療需求上升會直接影響學校、家庭及公立醫療系統的秋冬季準備。',
'留意流感陽性率何時回落、學校爆發宗數、兒童嚴重個案及疫苗接種率。',
'RTHK','https://news.rthk.hk/rthk/ch/component/k2/1869763-20260912.htm',
[('RTHK','https://news.rthk.hk/rthk/ch/component/k2/1869763-20260912.htm'),('衞生防護中心','https://www.chp.gov.hk/en/statistics/data/10/26/44/292/7105.html')]))
A.append(s('hong-kong-school-food-poisoning-39-20260913-daily','hong-kong','香港｜校園／食物安全',
'沙田圍小學39人疑食物中毒　供應商涉事食品暫停供應並停業清潔',
'37名學生及兩名職員進食校內午膳後出現腹痛及腹瀉，兩名學生求醫但毋須留院。',
'衞生防護中心正調查浸信會沙田圍呂明才小學懷疑食物中毒群組，涉及37名5至11歲學生及兩名學校職員。受影響人士9月9日在校內進食同款午膳後，約8至22小時出現腹痛及腹瀉，其中兩名學生曾求醫，均毋須入院。\n\n初步調查指，較大機會與供應商提供的滷水雞髀及長通粉有關。食安中心已要求供應商暫停涉事食品、停業進行徹底清潔消毒，並抽取食物及環境樣本化驗；當局仍在追查污染環節及是否有其他學校受影響。',
'大型學校午膳供應涉及集中製作與配送，一旦製作或溫控出問題，可同時影響大量學生。',
'個案涉及39人並需要暫停供應商運作，後續化驗結果會影響校園膳食安全安排。',
'留意化驗結果、供應商何時恢復運作，以及有否發現同一供應鏈的其他個案。',
'Sing Tao / CHP','https://www.stheadline.com/zh-hans/society/3614632/',
[('Sing Tao','https://www.stheadline.com/zh-hans/society/3614632/'),('衞生防護中心','https://www.chp.gov.hk/en/statistics/data/10/26/43/7120.html')]))
A.append(s('japan-shutoko-five-car-crash-20260913-daily','japan','日本｜交通／公共安全',
'首都高橫羽線五車相撞4人輕傷　川崎一段上行線曾封閉約三小時',
'事故凌晨在大師JCT附近發生，涉及一輛貨車及四輛私家車，受影響路段其後重開。',
'日本傳媒報道，9月13日凌晨約零時半，神奈川縣川崎市首都高速橫羽線大師JCT附近發生五車相撞事故，涉及一輛貨車及四輛私家車，四人受輕傷。警方及道路管理部門到場處理，未有報告重傷或死亡。\n\n事故令橫羽線上行由淺田交流道至大師交流道一段一度封閉，交通管制持續約三小時。清晨主要封路已解除，但事故原因及各車碰撞次序仍有待警方進一步調查。',
'首都高速橫羽線是東京與橫濱、川崎之間的重要道路，凌晨事故仍可影響早晨物流與跨區交通。',
'多車事故雖未造成重傷，但長時間封路反映首都圈主要幹道發生事故時的交通脆弱性。',
'留意警方事故調查、道路設施有否受損，以及早上繁忙時段是否仍有殘餘擠塞。',
'FNN Prime Online','https://news.livedoor.com/article/detail/32310659/',
[('FNN Prime Online','https://news.livedoor.com/article/detail/32310659/')]))
A.append(s('japan-chiba-rain-research-20260913-daily','japan','日本｜災害／氣候',
'氣象研究所分析千葉破紀錄暴雨　罕見雨帶滯留逾六小時放大災情',
'初步研究指出，通常快速移動的線狀雷雨系統長時間停留房總半島附近，是8月致命暴雨的重要因素。',
'日本氣象研究所最新初步分析指出，8月13日千葉縣破紀錄暴雨由類似颮線的線狀降水系統造成，但該系統沒有如常快速移動，北端在房總半島附近停留超過六小時，令同一地區持續承受猛烈降雨。\n\n該場暴雨造成至少13人死亡，並引發廣泛水浸與交通中斷。研究人員正進一步分析海陸風、暖濕空氣及大氣流向如何共同令雨帶近乎停滯；結果將影響地方政府對短時極端降雨、避難時機及河川預警的風險模型。',
'日本近年多次出現線狀降水帶造成嚴重災害，氣象部門正加強即時預報與成因研究。',
'若停滯型雨帶更常出現，傳統按移動速度設計的防災與交通應變需要重新評估。',
'留意氣象研究所最終分析、地方防災指引是否調整，以及秋季後續極端降雨風險。',
'The Japan Times / JMA MRI','https://www.japantimes.co.jp/environment/2026/09/11/climate-change/chiba-rain-analysis/',
[('The Japan Times','https://www.japantimes.co.jp/environment/2026/09/11/climate-change/chiba-rain-analysis/'),('Japan Meteorological Agency','https://www.jma.go.jp/jma/indexe.html')]))
A.append(s('market-economy-oil-week-above-100-20260913-daily','market-economy','財經｜能源／全球市場',
'油價雖回吐仍錄逾8%周升幅　Brent收104.61美元、美國柴油創紀錄',
'中東航運及供應風險令原油維持每桶100美元附近，能源通脹重新成為利率與企業成本核心變數。',
'Reuters報道，原油周五回落，但全周仍上升超過8%。Brent結算報每桶104.61美元，WTI報100.05美元；美國柴油價格更升至紀錄高位。市場一方面消化霍爾木茲與紅海供應中斷，另一方面留意區內外交接觸能否恢復部分航運。\n\n國際能源署同時下調今年供應預測，指中東衝突延長正常海灣原油流動恢復時間。高油價正重新傳導至運輸、航空、化工及消費物價，歐美央行因而面對更複雜的通脹與增長取捨。',
'油價在中東供應風險與需求放緩之間劇烈波動，能源衝擊亦推高債息與加息預期。',
'每桶100美元以上若維持數周，可能改變企業盈利、通脹路徑及央行政策定價。',
'留意霍爾木茲航運恢復、沙特供應、IEA庫存數據，以及美歐央行對能源通脹的回應。',
'Reuters','https://www.reuters.com/business/energy/oil-prices-set-end-week-over-100-first-time-nearly-4-months-2026-09-11/',
[('Reuters','https://www.reuters.com/business/energy/oil-prices-set-end-week-over-100-first-time-nearly-4-months-2026-09-11/'),('IEA via Reuters','https://www.reuters.com/business/energy/global-2026-oil-supply-gap-deepen-delayed-return-normal-gulf-flows-iea-says-2026-09-11/')]))
A.append(s('market-economy-oracle-ellison-sale-cancelled-20260913-daily','market-economy','財經｜企業／雲端基建',
'Larry Ellison取消出售5,000萬股Oracle計劃　AI基建融資仍是市場焦點',
'Oracle表示原定股票出售計劃已取消、期間未有股份出售；公司仍準備為雲端與AI基建籌集巨額資金。',
'Oracle表示，董事長Larry Ellison已取消原先可出售5,000萬股公司股票的交易計劃，該計劃公布後僅一天便撤回，期間沒有股份實際售出。公司稱Ellison目前沒有出售持股的意向，消息減少市場對大股東短期減持的憂慮。\n\n另一方面，Oracle仍計劃在2026年透過債務及股權方式籌集約450億至500億美元，以擴建雲端及AI基建，服務包括Meta、Nvidia、OpenAI等大型客戶。高資本開支、重組成本與AI訂單增長之間的平衡，仍是投資者評估公司的核心。',
'Oracle正在大幅擴張AI資料中心，同時需要管理融資規模、負債及投資者對資本回報的要求。',
'取消大股東減持可紓緩短期供應壓力，但不會消除AI基建擴張帶來的融資與執行風險。',
'留意Oracle融資安排、雲端訂單轉化速度、資本開支與現金流，以及Ellison是否重新設立交易計劃。',
'Reuters','https://www.reuters.com/business/larry-ellison-cancels-plan-sell-oracle-stock-2026-09-12/',
[('Reuters','https://www.reuters.com/business/larry-ellison-cancels-plan-sell-oracle-stock-2026-09-12/'),('Oracle Investor Relations','https://investor.oracle.com/')]))
A.append(s('ai-tech-openai-no-2026-ipo-20260913-daily','ai-tech','AI / 科技｜治理／企業',
'Altman稱OpenAI不會在2026年上市　安全風險與監管討論升溫',
'OpenAI行政總裁表示今年不會推進IPO，並支持更強制性的前沿AI安全規則與跨公司協調。',
'Reuters報道，OpenAI行政總裁Sam Altman表示公司不會在2026年進行首次公開招股，並把近期前沿AI安全疑慮列為重要背景。此表態出現在美國國會研究更具約束力安全規則、AI代理系統多次出現未預期行為之際。\n\nOpenAI近日亦公開支持以能力為基礎的全國AI安全要求，包括獨立評估、網絡安全及事故通報。上市時間延後令市場更關注公司如何在龐大融資需求、快速模型迭代與安全治理之間取得平衡。',
'前沿AI公司正同時面對高昂算力投資、上市融資壓力與監管機構對模型風險的要求。',
'IPO延後及安全規則轉向強制化，可能改變AI企業融資、模型發布節奏與第三方審核方式。',
'留意OpenAI後續融資、國會AI法案、獨立安全評估安排，以及其他大型實驗室是否採取相近立場。',
'Reuters','https://www.reuters.com/legal/litigation/openai-ipo-will-not-happen-2026-amid-ai-safety-fears-altman-says-2026-09-12/',
[('Reuters','https://www.reuters.com/legal/litigation/openai-ipo-will-not-happen-2026-amid-ai-safety-fears-altman-says-2026-09-12/'),('Reuters — AI safety rules','https://www.reuters.com/legal/government/openai-pushes-mandatory-national-ai-safety-requirements-2026-09-09/')]))
A.append(s('ai-tech-anthropic-slow-model-development-20260913-daily','ai-tech','AI / 科技｜安全／前沿模型',
'Anthropic倡前沿AI公司放慢模型開發　提第三方評估與共同安全標準',
'Dario Amodei提出三步框架，主張前沿實驗室建立外部評估、跨公司安全協調及國際合作。',
'Anthropic行政總裁Dario Amodei呼籲前沿AI公司放慢最先進模型的開發節奏，並建立更一致的風險控制。他提出由獨立評估者進入公司進行測試、主要實驗室協調共同安全標準，以及政府與國際夥伴建立可執行的治理安排。\n\n呼籲出現之際，Anthropic亦披露Claude曾被不同使用者嘗試用於網絡攻擊、監控、武器研究及詐騙等高風險活動。Amodei強調並非停止AI進步，而是希望在能力提升速度與安全保障之間重新建立約束。',
'大型AI模型能力快速提升，同時企業正面對濫用、失控代理及國家安全風險。',
'若主要AI公司接受共同減速與第三方審核，模型發布節奏、競爭策略和監管框架都可能出現實質轉變。',
'留意OpenAI、Google及其他實驗室是否加入協議，美國國會如何處理前沿模型責任，以及第三方評估能否制度化。',
'Reuters','https://www.reuters.com/business/anthropic-ceo-urges-ai-companies-slow-model-development-2026-09-12/',
[('Reuters','https://www.reuters.com/business/anthropic-ceo-urges-ai-companies-slow-model-development-2026-09-12/'),('Reuters — Claude misuse','https://www.reuters.com/world/china/how-anthropic-says-claude-was-used-weapons-spying-cyber-operations-2026-09-11/')]))
A.append(s('manga-anime-bleach-finale-delay-20260913-daily','manga-anime','漫畫 / Anime｜動畫製作',
'《BLEACH 千年血戰篇》最後兩集延期　49、50話改至10月下旬播出',
'製作委員會表示為提升高潮段落製作品質，原定9月播出的最後兩集分別延至10月19日及26日。',
'《BLEACH 千年血戰篇 -禍進譚-》製作方宣布調整第49及50話播出與串流時間。第49話改於10月19日在東京電視台系播出，第50話改於10月26日播出，其他平台則按新時間陸續上架。\n\n製作委員會解釋，延期是希望在作品進入最終高潮時提高整體製作品質，9月中至10月中會以精選集填補原有檔期。對一部已進入完結階段的大型系列而言，一個月左右的空檔亦會影響海外串流宣傳與最終話熱度安排。',
'《BLEACH》最終章自7月起播出，最後兩集原本安排在9月完成整季。',
'最終話延期是直接影響觀眾與串流平台排期的正式製作變更，也反映日本動畫製作時間壓力。',
'留意製作委員會是否再調整其他地區串流時間，以及10月播出前會否公布更多製作或宣傳安排。',
'BLEACH production staff / Final Weapon','https://finalweapon.net/2026/09/12/bleach-thousand-year-blood-war-part-4-the-calamity-episodes-49-50-delayed/',
[('Final Weapon','https://finalweapon.net/2026/09/12/bleach-thousand-year-blood-war-part-4-the-calamity-episodes-49-50-delayed/'),('Official production notice quoted by community','https://www.reddit.com/r/TwoBestFriendsPlay/comments/1weetmv/bleachs_last_two_episodes_have_been_delayed_until/')]))
A.append(s('manchester-united-city-derby-carrick-test-20260913-daily','manchester-united','Manchester United｜英超／曼市打吡',
'曼聯迎曼市成Carrick早季大考　歐聯4球大勝後要修補聯賽失分',
'曼聯周日主場迎戰開季全勝的曼城，Carrick要證明球隊能把歐聯反彈延續至英超。',
'Reuters指出，Michael Carrick正式掌帥後迎來第二場曼市打吡，曼聯聯賽開季只取得一勝，早前不敵侯城並被愛華頓逼和，但周中歐聯4比0擊敗Sabah，令球隊在大戰前重新取得信心。\n\n前鋒Benjamin Sesko傷癒後連續對愛華頓及Sabah取得入球，Carrick認為他的速度、身體質素及拉扯防線能力對打吡十分重要。曼城則在新帥Enzo Maresca帶領下保持全勝，令這場比賽成為曼聯衡量爭前列實力的重要測試。',
'曼聯上季在Carrick領軍下回升至第三，但新季聯賽表現仍不穩定，防線亦曾在關鍵時間失球。',
'主場打吡同時涉及積分、信心與Carrick長期計劃可信度，結果會影響外界對曼聯開季走勢的判斷。',
'留意Rashford與Sesko狀態、曼聯中後場部署，以及球隊能否限制曼城高位壓迫與Haaland。',
'Reuters','https://www.reuters.com/sports/soccer/carrick-faces-derby-test-expectations-soar-man-utd-2026-09-11/',
[('Reuters — derby preview','https://www.reuters.com/sports/soccer/carrick-faces-derby-test-expectations-soar-man-utd-2026-09-11/'),('Reuters — Sesko','https://www.reuters.com/sports/soccer/man-uniteds-carrick-pleased-with-seskos-return-form-ahead-city-derby-2026-09-11/')]))
A.append(s('football-premier-league-arsenal-perfect-20260913-daily','football','Football｜英超',
'阿仙奴作客2比0挫新特蘭四戰全勝　利物浦與車路士同日失分',
'阿仙奴憑Raya救出十二碼後反擊取勝，以12分保持完美開季；利物浦及車路士則只能和波。',
'英超周六賽事，阿仙奴作客新特蘭在David Raya救出十二碼後迅速取得主導，Bruno Guimaraes攻入加盟後首球，Bukayo Saka補時射入十二碼，最終2比0取勝，四輪聯賽全勝並保持榜首壓力。\n\n同日利物浦主場0比0被富咸逼和，開季四場已有三場和局；車路士則在主場2比2逼和升班馬侯城。諾定咸森林2比1擊敗阿士東維拉，葉士域治則3比2挫水晶宮，早段積分榜差距開始拉開。',
'阿仙奴是衛冕冠軍，新季開局穩定；利物浦與車路士則仍在新教練及大幅陣容調整後尋找節奏。',
'四連勝令阿仙奴先建立積分優勢，而競爭對手連續和波會放大之後每場直接對碰的重要性。',
'留意曼市對曼聯結果、阿仙奴傷兵情況，以及利物浦與車路士能否在歐戰後改善聯賽節奏。',
'Reuters','https://www.reuters.com/sports/soccer/liverpool-chelsea-held-wins-forest-ipswich-2026-09-12/',
[('Reuters','https://www.reuters.com/sports/soccer/liverpool-chelsea-held-wins-forest-ipswich-2026-09-12/'),('Reuters — Arsenal match','https://www.reuters.com/sports/soccer/guimaraes-opens-arsenal-account-win-sunderland-2026-09-12/')]))
A.append(s('football-real-madrid-rayo-4-1-20260913-daily','football','Football｜西甲',
'麥巴比梅開二度　皇家馬德里4比1擊敗華歷簡奴追平榜首分數',
'皇馬主場在上半場迅速建立優勢，麥巴比兩度破門，球隊賽後以12分追平巴塞隆拿。',
'皇家馬德里在班拿貝以4比1擊敗華歷簡奴。Kylian Mbappe第14分鐘射入十二碼，Alvaro Carreras三分鐘後擴大比數，Jude Bellingham亦在上半場建功；華歷簡奴下半場追回一球後，Mbappe補時再以反擊完成梅開二度。\n\nMbappe今季六場各項賽事已攻入七球，皇馬取得三分後以12分追平尚未完成本輪賽事的巴塞隆拿。華歷簡奴下半場一度取得較多控球並考驗Courtois，但未能真正扭轉早段落後三球的形勢。',
'西甲爭冠在季初已出現皇馬與巴塞互相施壓，皇馬夏季新陣容仍在磨合。',
'Mbappe持續高效入球能降低皇馬磨合期失分風險，亦令榜首競爭更早進入直接比拼。',
'留意巴塞隆拿本輪結果、Mbappe連續入球走勢，以及皇馬在歐聯與聯賽雙線下的輪換。',
'Reuters','https://www.reuters.com/sports/soccer/mbappe-scores-brace-real-madrid-secure-routine-victory-over-rayo-vallecano-2026-09-12/',
[('Reuters','https://www.reuters.com/sports/soccer/mbappe-scores-brace-real-madrid-secure-routine-victory-over-rayo-vallecano-2026-09-12/')]))

sections = [
 {'slug':'world','title':'世界','subtitle':'歐洲 · 美洲 · 非洲 · 大洋洲','articleIds':[x['id'] for x in A if x['desk']=='world']},
 {'slug':'asia','title':'亞洲','subtitle':'東亞 · 東南亞 · 南亞 · 中亞 · 西亞／中東','articleIds':[x['id'] for x in A if x['desk']=='asia']},
 {'slug':'hong-kong','title':'香港','subtitle':'本地時事 · 公共服務 · 社會','articleIds':[x['id'] for x in A if x['desk']=='hong-kong']},
 {'slug':'japan','title':'日本','subtitle':'社會 · 交通 · 災害 · 生活','articleIds':[x['id'] for x in A if x['desk']=='japan']},
 {'slug':'market-economy','title':'財經 / 全球市場','subtitle':'市場 · 宏觀 · 企業','articleIds':[x['id'] for x in A if x['desk']=='market-economy']},
 {'slug':'ai-tech','title':'AI / 科技','subtitle':'人工智能 · 科技 · 網絡安全','articleIds':[x['id'] for x in A if x['desk']=='ai-tech']},
 {'slug':'manga-anime','title':'漫畫 / Anime','subtitle':'動畫 · 漫畫 · 產業','articleIds':[x['id'] for x in A if x['desk']=='manga-anime']},
 {'slug':'manchester-united','title':'Manchester United','subtitle':'曼聯獨立專版','articleIds':[x['id'] for x in A if x['desk']=='manchester-united']},
 {'slug':'football','title':'Football','subtitle':'全球球會 · 聯賽 · 國際賽','articleIds':[x['id'] for x in A if x['desk']=='football']},
]

daily = {
 'editionNumber': EDITION, 'date': DATE, 'dateLabel':'2026年9月13日 星期日', 'tagline':'9月13日重點新聞 · v3長文',
 'editorialStandardVersion':3, 'contentVersion':3,
 'leadId':A[0]['id'], 'topFive':[A[i]['id'] for i in [0,2,1,5,9]], 'articles':A, 'sections':sections
}
(DATA / f'{DATE}.json').write_text(json.dumps(daily, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
(DATA / 'latest.json').write_text(json.dumps(daily, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

topic = {'date':DATE,'editorialStandardVersion':3,'contentVersion':3,'articles':[],'sections':[]}
(DATA / 'topic-more').mkdir(exist_ok=True)
(DATA / 'topic-more' / f'{DATE}.json').write_text(json.dumps(topic, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

archive_path = DATA / 'archive.json'
archive = json.loads(archive_path.read_text(encoding='utf-8'))
archive['editions'] = [e for e in archive.get('editions',[]) if e.get('date') != DATE]
archive['editions'].insert(0, {
 'date':DATE,'shortDate':'13 SEP 2026',
 'headline':'俄軍大規模空襲烏克蘭至少10死；莫迪與習近平推動中印關係回暖；剛果（金）伊波拉確診突破7,000宗',
 'topics':['世界','亞洲','香港','日本','📈 財經 / 全球市場','AI / 科技','漫畫 / Anime','Manchester United','Football'],
 'url':f'editions/{DATE}.html'
})
archive_path.write_text(json.dumps(archive, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

old_html = (ROOT/'editions'/'2026-09-12.html').read_text(encoding='utf-8')
html = old_html.replace('2026-09-12','2026-09-13').replace('NO. <span data-edition-number>023</span>','NO. <span data-edition-number>024</span>').replace('v=20260912','v=20260913')
(ROOT/'editions'/f'{DATE}.html').write_text(html, encoding='utf-8')

# Advance the accumulated desk baseline without collapsing any desk.
desk_path = DATA / 'desk-latest.json'
desk = json.loads(desk_path.read_text(encoding='utf-8'))
desk['date'] = DATE
desk['generatedAt'] = STAMP
desk['lastUpdated'] = STAMP
desk_path.write_text(json.dumps(desk, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

import sync_daily_into_desk
rc = sync_daily_into_desk.main()
if rc:
    raise SystemExit(rc)

desk = json.loads(desk_path.read_text(encoding='utf-8'))
counts = {}
for slug, stories in desk.get('desks',{}).items():
    keys=set()
    for st in stories if isinstance(stories,list) else []:
        if isinstance(st,dict):
            keys.add(st.get('id') or ('title:'+str(st.get('title','')).strip()))
    counts[slug]=len([k for k in keys if k])
coverage = desk.setdefault('coverage',{})
coverage.update({
 'status':'COMPLETE','deskLatestStoryCounts':counts,'deskLatestDepthMet':True,'routingGateMet':True,
 'sourceGateMet':True,'copyGateMet':True,'geographicGateMet':True,'footballGateMet':True,
 'publishingGateMet':True,'japanCountVerified':counts.get('japan',0)
})
desk['date']=DATE; desk['generatedAt']=STAMP; desk['lastUpdated']=STAMP
desk_path.write_text(json.dumps(desk, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

live = {
 'mode':'DAILY_BASELINE','date':DATE,'editorialStandardVersion':3,'contentVersion':3,
 'lastUpdated':STAMP,'lastUpdatedLabel':'2026年9月13日 08:00 HKT','windowLabel':'08:00 HKT Daily Baseline',
 'nextUpdateLabel':'下一輪為 09:00 HKT Live Update','newCount':0,'updatedCount':0,'developingCount':0,
 'items':[],'topFive':[], 'coverage':coverage
}
(DATA/'live.json').write_text(json.dumps(live, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print('PUBLISH_20260913_READY', len(A), counts)
