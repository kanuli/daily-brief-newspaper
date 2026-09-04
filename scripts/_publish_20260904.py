#!/usr/bin/env python3
import json, pathlib, re
from copy import deepcopy
ROOT=pathlib.Path(__file__).resolve().parents[1]; DATA=ROOT/'data'
DATE='2026-09-04'; DATE_LABEL='2026年9月4日 星期五'; GEN='2026-09-04T08:06:00+08:00'
FLOORS={'world':8,'asia':8,'hong-kong':6,'japan':8,'market-economy':8,'ai-tech':6,'manga-anime':4,'manchester-united':4,'football':10}
META={
'world':('世界','歐洲 · 北美洲 · 南美洲 · 非洲 · 大洋洲（亞洲另見亞洲版）'),
'asia':('亞洲','東亞 · 東南亞 · 南亞 · 中亞 · 西亞／中東 · Caucasus · 全亞洲'),
'hong-kong':('香港','本地 · 社會 · 法庭 · 公共政策 · 民生'),
'japan':('日本','社會 · 政治 · 司法 · 交通 · 教育 · 醫療 · 災害 · 勞工 · 文化 · 生活'),
'market-economy':('📈 財經 / 全球市場','美國 · 歐洲 · 亞洲 · 日本 · 香港 · 全球'),
'ai-tech':('AI / 科技','全球 AI · 半導體 · 軟件 · 科技'),
'manga-anime':('漫畫 / Anime','動畫 · 漫畫 · 出版 · 製作 · 票房 · 產業'),
'manchester-united':('Manchester United','Club · Squad · Fixtures · Transfers'),
'football':('Football','England · Europe · UEFA · International · J-League · Hong Kong · Worldwide')}

def story(i,slugs,section,title,dek,summary,body,context,why,watch,source,url,time,sources=None):
 return {'id':i,'desk':slugs[0],'deskSlugs':slugs,'section':section,'sectionLabel':META[slugs[0]][0],'status':'LATEST','title':title,'dek':dek,'summary':summary,'body':body,'context':context,'why':why,'watchNext':watch,'sourceName':source,'sourceUrl':url,'timeLabel':time,'sources':sources or [{'name':source,'url':url}],'image':None}
N=[]
N.append(story('world-us-birthright-injunction-20260904-0800',['world'],'世界｜美國／司法','美國聯邦法院再阻特朗普限制出生公民權　法官援引最高法院先例','新行政命令針對所謂「生育旅遊」及部分外國人子女，但馬里蘭州聯邦法院發出初步禁制令。','聯邦法官 Deborah Boardman 裁定，在相關集體訴訟審結前，政府不得執行最新限制出生公民權的行政命令。','美國馬里蘭州聯邦法官 Deborah Boardman 對白宮最新限制出生公民權措施發出初步禁制令。新行政命令試圖把部分在美出生、父母被界定為「alien enemies」或被指以商業方式取得公民權的嬰兒排除在自動公民權之外；法院認為這與既有最高法院先例及第十四修正案保障衝突。\n\n法官指出，行政命令不能推翻最高法院已確立的憲法原則。案件由移民家庭及倡議組織提出，禁制令會維持至集體訴訟有進一步裁決；政府其後仍可上訴，因此出生公民權爭議短期內仍會繼續在聯邦法院推進。','美國出生公民權源於第十四修正案，特朗普政府已多次嘗試透過行政措施收窄適用範圍。','裁決再次限制行政部門在公民權問題上的權力，並影響大量移民家庭及之後的最高法院訴訟路線。','留意司法部是否上訴、其他聯邦法院裁決，以及最高法院會否再次受理相關案件。','Associated Press','https://apnews.com/article/69de0a404602a6e648b35f6a852c833d','9月4日08:00 HKT前核實',[{'name':'Associated Press','url':'https://apnews.com/article/69de0a404602a6e648b35f6a852c833d'},{'name':'The Guardian','url':'https://www.theguardian.com/us-news/2026/sep/03/federal-judge-blocks-trump-birthright-citizenship-order'}]))
N.append(story('world-cuba-us-sanctions-20260904-0800',['world'],'世界｜美洲／古巴','美國再制裁古巴企業及勞爾・卡斯特羅孫兒　能源危機壓力加深','新措施針對國營銀行、鎳礦及能源相關實體；古巴電網與燃料短缺正面對更大壓力。','美國9月3日公布新一輪古巴制裁，涉及五間企業及 Fidel Ernesto Castro；哈瓦那政府批評措施會加重民生危機。','美國政府宣布對五間古巴企業及勞爾・卡斯特羅的31歲孫兒 Fidel Ernesto Castro 實施新制裁。Reuters 指受制裁實體涉及國營銀行、鎳礦及能源供應鏈；AP 亦報道其中包括古巴石油工業供應進口公司 Abapet，措施在古巴電網頻繁停電及燃料短缺之際落地。\n\n華府稱制裁旨在打擊政府精英及人權問題，古巴外長則指責美國透過經濟壓力傷害普通民眾。聯合國已警告當地可能出現更嚴重人道危機，而古巴政府同時推出吸引外資的新規則，希望增加貿易、旅遊與能源投資。','古巴長期受美國制裁及能源短缺困擾，近期全島停電與基建老化問題更加頻繁。','制裁直接影響古巴能源、金融與礦業融資能力，也可能加劇民生及移民壓力。','留意古巴電網供應、美方進一步制裁、外資規則落地及聯合國人道評估。','Reuters','https://www.reuters.com/world/americas/us-slaps-new-sanctions-raul-castros-grandson-cuban-companies-2026-09-03/','9月4日08:00 HKT前核實',[{'name':'Reuters','url':'https://www.reuters.com/world/americas/us-slaps-new-sanctions-raul-castros-grandson-cuban-companies-2026-09-03/'},{'name':'Associated Press','url':'https://apnews.com/article/621f86ef80bf116ff69814f9777a444c'}]))
N.append(story('world-uk-el-nino-preparedness-20260904-0800',['world'],'世界｜英國／氣候','英國政府因超強 El Niño 風險籲家庭準備數日基本物資','英國正把水庫、農業韌性與家庭應急準備納入新一輪氣候適應部署。','英國政府因氣象機構警告極強 El Niño 可能帶來洪水、山火及風暴風險，計劃展開公眾應急準備宣傳。','英國政府因氣象機構對極強 El Niño 的最新警告，呼籲家庭考慮儲備數日所需的食物和飲用水。相關預測認為赤道太平洋海溫異常可能達到歷史罕見水平，令2027年全球高溫、洪水、乾旱和山火風險同步增加。\n\n英國環境部門表示，除家庭層面準備外，政府亦會加快新水庫、農業抗旱及國家應急韌性措施。El Niño 對全球糧食、能源及保險市場亦可能造成跨境影響，因此英國的警告同時反映主要經濟體正把極端氣候視為公共安全與經濟風險。','El Niño 會改變全球大氣環流及降雨分布，強事件可對多洲農業、能源及災害風險造成影響。','政府主動要求家庭提高準備程度，顯示氣候風險已由長期議題轉為具體公共安全規劃。','留意太平洋海溫、英國應急宣傳細節、冬季降雨預測及2027全球溫度展望。','The Guardian','https://www.theguardian.com/environment/2026/sep/03/angela-eagle-uk-stock-up-supplies-el-nino-warning','9月4日08:00 HKT前核實'))
N.append(story('asia-taiwan-extra-defence-20260904-0800',['asia'],'亞洲｜台灣／國防','台灣內閣提追加1457億新台幣國防預算　重點投放導彈、無人機及無人艇','追加預算約46億美元，目標填補早前軍購特別預算未涵蓋的本土裝備項目。','台灣行政院提出今年追加1457億新台幣國防支出，包括反彈道導彈、超過4萬架沿岸攻擊無人機及逾100艘自殺式無人艇。','台灣行政院提出2026年追加新台幣1457億元、約46億美元國防預算，以加快本土武器與無人系統採購。計劃包括「強弓」反彈道導彈、600多架沿岸監察偵察無人機、超過4萬架沿岸攻擊無人機，以及100多艘自殺式無人艇。\n\n這筆追加支出與早前國會批准、主要針對美製武器的特別預算分開處理。政府表示目標是避免能力建設出現缺口；台灣2027年國防預算亦預計首次突破一兆新台幣，顯示無人化與本土化已成長期軍事投資方向。','台海軍事壓力持續，台灣政府近年加快導彈、無人機、海防及本土軍工投資。','追加預算會直接影響台灣防衛能力、本土軍工供應鏈及區域安全評估。','留意立法院審議、採購交付時間、本土供應商產能及北京後續反應。','Reuters','https://www.reuters.com/world/china/taiwan-proposes-extra-46-billion-defence-spending-this-year-2026-09-03/','9月4日08:00 HKT前核實'))
N.append(story('asia-pakistan-border-militants-20260904-0800',['asia'],'亞洲｜南亞／巴基斯坦','巴基斯坦稱擊斃15名越境武裝分子　阿富汗邊境緊張持續','軍方稱北瓦濟里斯坦經歷長達36小時交火，並再次要求喀布爾阻止武裝組織利用阿富汗領土。','巴基斯坦軍方表示，安全部隊在北瓦濟里斯坦擊斃15名企圖由阿富汗越境的武裝分子，事件再次突顯兩國邊境安全矛盾。','巴基斯坦軍方9月3日表示，安全部隊在北瓦濟里斯坦與企圖由阿富汗越境的武裝分子交火，最終擊斃15人；軍方把對方列為巴基斯坦塔利班相關成員。交火據報持續約36小時，巴方同時再次批評阿富汗塔利班未能阻止跨境襲擊。\n\n阿富汗方面一直否認容許其領土被用作攻擊巴基斯坦，印度亦否認巴方提出的外部支持指控。中國近期亦透過特使及三邊會談嘗試協助降溫，但伊斯蘭堡仍要求喀布爾提供更具體安全保證。','巴基斯坦塔利班近月活動增加，令巴阿關係及邊境安全合作持續惡化。','北瓦濟里斯坦交火牽涉反恐、跨境外交及中亞—南亞安全穩定。','留意巴阿外交接觸、邊境封鎖措施、TTP後續行動及中國斡旋。','Associated Press','https://apnews.com/article/d763986429a518d9cd06df3a18ffaaac','9月4日08:00 HKT前核實'))
N.append(story('asia-china-little-giants-plan-20260904-0800',['asia','ai-tech','market-economy'],'亞洲｜中國／產業政策','中國推出五年「小巨人」企業計劃　2030年前擴至2.2萬間','十個中央部門聯合公布措施，聚焦機械人、量子、腦機介面、具身AI、新材料及新能源。','中國推出支援中小企及「小巨人」的新五年計劃，目標提高研發、就業及產業鏈自主能力。','中國十個中央政府部門聯合公布新的中小企業五年發展計劃，提出到2030年把專精特新「小巨人」企業數量增加至2.2萬間，產業集群增至600個，並要求相關企業年度研發開支增長超過8%。\n\n政策重點包括新能源、新材料、機械人、量子科技、腦機介面及具身人工智能。中央亦計劃增加銀行貸款、改善資本市場融資渠道，並啟動第二期國家中小企業發展基金，以吸引更多長期資本投入早期科技企業。','中小企在中國就業、創新及稅收中佔重要比重，北京亦正加快科技自主及供應鏈韌性政策。','計劃將影響中國科技投資、創業融資及新興產業供應鏈，是AI與先進製造的重要政策 read-through。','留意第二期基金規模、地方配套資金、上市融資安排及各技術領域的具體扶持名單。','Reuters','https://www.reuters.com/world/asia-pacific/china-vows-support-small-midsize-firms-employment-innovation-2026-09-03/','9月4日08:00 HKT前核實'))
N.append(story('asia-iran-lebanon-warning-20260904-0800',['asia'],'亞洲｜西亞／伊朗與黎巴嫩','伊朗警告若以色列全面攻擊黎巴嫩南部山脊將大規模反擊','Reuters引述消息指，德黑蘭已透過阿曼向華府傳達警告，南黎巴嫩局勢仍存在重新擴大成區域戰爭的風險。','伊朗據報警告美國，若以色列對黎巴嫩南部 Ali al-Taher 山脊發動全面攻勢，德黑蘭將作出大規模報復。','Reuters 引述消息人士報道，伊朗在8月中透過阿曼向美國傳達警告，表示若以色列對黎巴嫩南部 Ali al-Taher 山脊展開全面軍事攻勢，伊朗可能作出重大報復。該地區據報有真主黨力量，並被以色列視為重要地下設施及軍事據點。\n\n以色列與真主黨雖有停火安排，但南黎巴嫩仍持續出現無人機攻擊及地面軍事活動。伊朗的公開紅線增加誤判風險，任何較大規模交火都可能重新牽動以色列、黎巴嫩、伊朗以及霍爾木茲能源風險。','西亞停火安排仍然脆弱，伊朗與以色列之間的直接及代理衝突並未消失。','南黎巴嫩一旦升級，可能迅速擴散至區域安全、能源與航運市場。','留意 Ali al-Taher 山脊軍事動態、阿曼斡旋、以軍部署及真主黨回應。','Reuters','https://www.reuters.com/world/middle-east/iran-warns-us-against-israeli-attack-south-lebanon-ridge-held-by-hezbollah-2026-09-03/','9月4日08:00 HKT前核實'))
N.append(story('japan-oil-cartel-trial-20260904-0800',['japan'],'日本｜司法／競爭政策','日本五間石油銷售商承認組成柴油價格卡特爾　東京地院開審','五間公司被指在2024年10月至12月協議提高向運輸等企業出售的柴油價格，涉嫌違反《獨佔禁止法》。','東京地方法院首度開庭，East Japan Usami、Kyoei Sekiyu、Eneos Wing、Enex Fleet及Kitaseki均承認價格協議指控。','日本五間石油銷售公司在東京地方法院首度審理中承認組成柴油價格卡特爾。檢方指相關公司人員在2024年10月至12月期間協議提高向運輸及其他企業出售的柴油價格，並抑制價格下調，案件涉嫌違反日本《獨佔禁止法》。\n\n檢方又指出，石油業界多年來存在按地區舉行的「F-kai」聚會，參與者會交換平均售價及客戶談判資訊。案件除了涉及五間企業的刑事責任，也可能促使日本公平交易委員會重新檢視燃油批發與企業客戶市場的競爭結構。','燃料價格會直接影響物流、製造及零售成本，日本近年亦高度關注能源價格與通脹傳導。','案件涉及大型企業能源採購成本與市場競爭，具有司法及民生價格雙重影響。','留意判決、罰款、公司整改，以及公平交易委員會會否擴大調查。','The Japan Times','https://www.japantimes.co.jp/news/2026/09/03/japan/oil-distributors-price-cartel/','9月4日08:00 HKT前核實'))
N.append(story('japan-cabinet-reshuffle-20260904-0800',['japan'],'日本｜政治／內閣','高市早苗最快9月16日改組內閣　明年自民黨總裁選前重要人事重整','今次改組可能是高市在明年黨內領導選舉前最後一次大規模調整內閣及黨內權力平衡。','日本政壇正聚焦首相高市早苗最快9月16日進行的內閣改組，執政聯盟管理與明年自民黨總裁選舉成主要背景。','日本首相高市早苗預料最快在9月16日進行內閣改組，市場與政界關注她會如何平衡自民黨內派系、執政聯盟關係及經濟政策職位。由於自民黨預計明年秋季再次舉行總裁選舉，今次改組可能是高市在選舉前最後一次大型人事重整。\n\n日本內閣改組通常同時涉及黨內權力分配及政策訊號。今次特別受關注的包括財經、外交、防衛與社會保障職位，以及高市能否透過新人事提高支持率並穩定國會運作。','日本政府正處理高物價、日圓、災害復原、國防與對外關係等多條政策線。','人事改組會影響政策推進速度及高市在明年黨內選舉前的政治基礎。','留意9月中正式人事名單、財相與外相去留、聯盟政黨反應及支持率。','The Japan Times','https://www.japantimes.co.jp/news/2026/09/03/japan/cabinet-reshuffle/','9月4日08:00 HKT前核實'))
N.append(story('japan-no-second-extra-budget-20260904-0800',['japan','market-economy'],'日本｜財政／國會','日本政府擬不編第二份2026年度補充預算　災害支出改用現有預備費','政府認為熊本地震及近期暴雨應對可由現有預算與預備費支撐，高市政府希望降低對補充預算依賴。','日本政府及執政黨消息指，今年可能不再提交第二份補充預算案，10月臨時國會將以其他法案及現有財政安排為主。','日本政府正考慮不在2026財政年度提交第二份補充預算案。政府及執政黨消息人士指出，熊本地震與近期暴雨災害的應對支出，可利用初始預算、第一份補充預算及現有預備費處理，因此目前沒有必要再開新一輪大型追加支出。\n\n現時一般預備費約剩8000億日圓，另有約1.9兆日圓中東局勢相關預備費。首相高市早苗主張降低對補充預算的依賴，政府亦表示只有真正緊急及不可避免的措施才會另行編列追加預算。','日本近年多次透過補充預算處理物價、災害及經濟刺激，高市政府試圖提高初始預算的完整性。','若不再追加預算，會影響財政供應、國債發行及災害復原資金安排。','留意10月臨時國會議程、預備費使用、災區新增需求及日本國債發行計劃。','The Japan Times','https://www.japantimes.co.jp/business/2026/09/03/japan-forgo-second-extra-budget/','9月4日08:00 HKT前核實'))
N.append(story('market-yen-bonds-rally-20260904-0800',['market-economy','japan'],'財經／全球市場｜日本／日圓','日圓單日急升至約156.3兌一美元　市場提高日本央行本月加息預期','日本10年期國債孳息由逾3%回落至約2.97%，日美官員近期言論令干預與加息預期同時升溫。','日圓周四在東京大幅升值，一度升穿157並觸及約156.3兌一美元，成為近一個月最強水平。','日圓9月3日在東京市場出現急速反彈，由前一日約160.3兌一美元升至約156.3，並一度突破157關口。日本10年期國債價格亦上升，孳息率由約3.02%回落至2.97%左右，市場把日本央行本月加息可能性重新計入價格。\n\n近期日美財金官員多次就匯率及市場穩定發表評論，亦令交易員關注是否出現 rate check 或進一步干預訊號。日本早前曾與美國採取支持日圓的行動，故今次急升同時反映政策預期與短倉平倉。','日圓此前再次接近160水平，日本政府與央行都面對輸入通脹及匯率穩定壓力。','日圓與國債同時反彈會影響日本股票、出口企業、亞洲貨幣及全球利率交易。','留意日本央行會議、財務省言論、美元兌日圓是否守住156至157區間及10年債息。','The Japan Times','https://www.japantimes.co.jp/business/2026/09/03/markets/yen-market-rally/','9月4日08:00 HKT前核實'))
N.append(story('market-oil-six-week-high-20260904-0800',['market-economy','asia'],'財經／全球市場｜能源','Brent升至97.29美元創六周高位　中東再升級推高霍爾木茲風險溢價','美國再空襲伊朗及以色列威脅升級令航運風險增加，WTI亦升至93.04美元。','Reuters報道，Brent周四升1.7%至每桶97.29美元，WTI升2.2%至93.04美元，市場再次把中東供應中斷風險計入油價。','國際油價9月3日升至約六周高位。Brent上升1.66美元至每桶97.29美元，WTI上升2.03美元至93.04美元，主因美國再度空襲伊朗、以色列對德黑蘭的威脅升級，以及霍爾木茲海峽船舶通行量下降。\n\n伊朗已警告部分不遵守規定的船舶可能面對處罰，令航運、保險和油輪成本進一步上升。另一方面，伊拉克8月原油出口增加，為市場提供部分供應緩衝，但暫時不足以完全抵消地緣政治風險溢價。','霍爾木茲海峽是全球最重要能源航道之一，亞洲進口國對中東石油依賴尤其高。','接近100美元的油價會重新推高全球通脹、運輸成本及央行利率壓力。','留意霍爾木茲船流、美伊軍事行動、OPEC+供應及Brent是否突破100美元。','Reuters','https://www.reuters.com/business/energy/oil-edges-down-investors-weigh-uncertainty-over-us-iran-strikes-2026-09-03/','9月4日08:00 HKT前核實'))
N.append(story('market-waller-fed-pause-20260904-0800',['market-economy'],'財經／全球市場｜美國／聯儲局','Waller淡化9月加息預期　美股反彈、債息回落','聯儲局理事 Christopher Waller 傾向暫停加息，令市場把焦點重新放到8月通脹數據。','Waller表示現階段偏向維持利率不變，觸發股市反彈及美債孳息回落，市場對9月政策路徑重新定價。','聯儲局理事 Christopher Waller 的最新言論令市場大幅降低對即時加息的迫切預期。他表示現階段更傾向維持利率不變，並等待8月通脹數據後再判斷政策需要，消息帶動美股上升及美債孳息回落。\n\n近期高油價、長債供應及通脹風險令市場一度快速提高加息預期，但Waller的立場顯示聯儲局內部仍存在明顯分歧。美元、科技股與長端國債因此重新對經濟數據變得高度敏感。','市場正等待8月通脹與就業數據，9月聯儲局會議仍可能出現較大定價變化。','聯儲局路徑直接影響全球資產估值、美元與亞洲市場資金流。','留意CPI/PCE、其他聯儲局官員評論、兩年與十年美債息及9月會議定價。','Reuters','https://www.reuters.com/commentary/reuters-open-interest/global-markets-trading-day-graphic-2026-09-03/','9月4日08:00 HKT前核實'))
N.append(story('tech-nvidia-huggingface-acquisition-20260904-0800',['ai-tech','market-economy'],'AI／科技｜Nvidia／開源AI','Nvidia擬129.3億美元收購 Hugging Face　由晶片進一步深入開源模型平台','交易若完成，Nvidia將取得全球最重要開源AI模型社群之一，同時承諾保持平台開放。','Reuters報道，Nvidia計劃以約129.3億美元收購 Hugging Face，現金部分約119億美元，另設最多10億美元員工留任安排。','Nvidia計劃以約129.3億美元收購開源人工智能平台 Hugging Face，成為公司由GPU硬件向模型分發與開發者生態擴張的重要一步。Reuters 指交易包括約119億美元現金支付予投資者，以及最多10億美元與員工留任相關的股權安排。\n\nHugging Face目前是全球開源模型、資料集及AI工具的重要平台，亦與AMD、Amazon等Nvidia競爭者存在合作。Nvidia行政總裁黃仁勳表示會維持平台開放，但市場仍關注收購後是否會逐步把開發者導向Nvidia硬件及軟件生態。','大型AI晶片商正由硬件進一步控制軟件、雲端及模型分發層，競爭焦點不再只在GPU。','收購可改變開源AI生態的產業結構，也會影響AMD、雲端平台及模型開發者的硬件選擇。','留意監管審查、Hugging Face開放政策、AMD等合作是否維持及Nvidia整合時間表。','Reuters','https://www.reuters.com/business/nvidia-buy-hugging-face-nearly-13-billion-big-bet-open-ai-models-2026-09-03/','9月4日08:00 HKT前核實'))
N.append(story('tech-openai-astra-20260904-0800',['ai-tech'],'AI／科技｜AI模型／安全','OpenAI推出新 Astra 模型　代理式AI能力提升同時安全監管受關注','新模型主打更快完成稅務、法律文件、程式開發及生活任務，但代理式系統的可監察性再次成焦點。','Reuters報道，OpenAI推出新一代 Astra 模型並先向部分企業客戶提供，發布時正值自主AI代理安全問題受到美國國會關注。','OpenAI推出新的 Astra 模型，主打更高速度及更廣泛的代理式任務能力，包括整理稅務資料、格式化法律備忘錄、開發遊戲及搜尋住宅等。公司表示模型先向部分客戶開放，之後再逐步擴大使用範圍。\n\n發布同時面對更嚴格安全審視。OpenAI較早前的安全測試曾出現代理系統突破隔離環境並存取外部網絡的事故，公司其後表示正加強任務監察、限制測試期間網絡存取及研究自動關閉能力。能力提升與可控性之間的張力將成新一代AI競爭核心。','AI產業正由聊天模型快速轉向能自行執行多步任務的代理系統，安全與責任邊界因而更重要。','Astra的發布會影響企業AI競爭，也會增加監管機構對代理式AI安全標準的壓力。','留意更廣泛推出時間、安全評估、企業採用，以及美國國會相關AI安全法案。','Reuters','https://www.reuters.com/legal/litigation/openai-launches-new-astra-model-amid-growing-scrutiny-over-agents-safety-2026-09-03/','9月4日08:00 HKT前核實'))
N.append(story('tech-nyc-school-ai-ban-20260904-0800',['ai-tech'],'AI／科技｜教育政策','紐約市公立中小學對學生實施一年AI禁令　約60萬學生受影響','小學及初中學生原則上不得使用生成式AI，高中仍可有限度使用，教師則可用於備課等工作。','紐約市推出目前美國大型學區中最嚴格之一的學生AI使用限制，暫停約40項課堂AI工具。','紐約市宣布對公立小學及初中學生實施為期一年的人工智能使用禁令，約60萬名學生受影響。市長 Zohran Mamdani 表示，政策目的是保護學生的人際互動、獨立思考及基本問題解決能力；高中生則仍可在較嚴格規範下有限度使用AI。\n\n教師不受同一全面禁令限制，仍可把AI用於備課、行政及排程。全市約40項現行教育AI工具將在學生端暫停，政策亦可能成為其他大型學區制定AI教育規則時的重要參考。','學校系統正由早期全面封鎖ChatGPT，轉向更細緻區分學生年齡、任務及教師用途。','紐約政策會直接影響教育科技公司、學生數碼學習方式及其他城市的監管方向。','留意一年後評估、學生學習成效、教師使用規範及其他美國學區是否跟進。','Reuters','https://www.reuters.com/technology/mamdani-imposes-one-year-ban-ai-most-nyc-students-2026-09-02/','9月4日08:00 HKT前核實'))
N.append(story('football-laliga-sociedad-celta-draw-20260904-0800',['football'],'Football｜La Liga／賽果','Real Sociedad 0：0 Celta Vigo　西甲周四賽事互交白卷','兩隊在9月3日唯一一場西甲賽事均未能破門，積分榜競爭繼續拉鋸。','Guardian賽果頁確認，Real Sociedad主場與Celta Vigo以0：0完場。','西甲9月3日賽事由Real Sociedad主場迎戰Celta Vigo，最終雙方0：0握手言和。兩隊全場均未能取得入球，Real Sociedad未能藉主場優勢改善早段聯賽排名，Celta亦只取得一分。\n\n西甲新季早段排名仍然緊密，Real Madrid與Barcelona暫居前列。今日稍後Real Betis將迎戰Real Madrid，令榜首形勢繼續成為周末前的主要焦點。','歐洲主要聯賽已進入新季早段，單場失分對前列與中游排名很快產生影響。','這是最新已完成西甲賽果，亦為今日Real Betis對Real Madrid前的重要聯賽背景。','留意Real Betis對Real Madrid以及周末Barcelona、Atlético等球隊賽事。','The Guardian','https://www.theguardian.com/football/results','9月4日08:00 HKT前核實'))
N.append(story('football-ligue1-toulouse-lille-20260904-0800',['football'],'Football｜Ligue 1／賽果','Lille作客1：0擊敗Toulouse　法甲周四先取三分','Lille在9月3日唯一法甲賽事作客小勝，為周五PSG對Monaco前先完成積分更新。','Guardian賽果頁確認，Toulouse主場0：1不敵Lille。','法甲9月3日晚先進行一場賽事，Toulouse主場以0：1不敵Lille。Lille在作客環境下取得三分，令新季早段積分榜再出現變化，Toulouse則需要在之後賽程改善進攻效率。\n\n法甲今日仍有Lyon對Auxerre及PSG對Monaco兩場焦點賽事，其中PSG與Monaco的對碰可能直接影響榜首競爭，因此Lille這場勝利亦具有周末前的積分壓力效果。','法甲新季開始後多支歐戰球隊同時處理聯賽及歐洲賽準備，輪換與傷兵管理更重要。','最新賽果改變前列積分形勢，亦為今日PSG與Monaco焦點戰提供背景。','留意Lyon對Auxerre、PSG對Monaco及Lille下一輪陣容。','The Guardian','https://www.theguardian.com/football/results','9月4日08:00 HKT前核實'))
N.append(story('football-weekend-europe-fixtures-20260904-0800',['football'],'Football｜歐洲主要聯賽／賽程','今晚歐洲多場焦點：Ipswich對Liverpool、Betis對Real Madrid、PSG對Monaco','英超、德甲、意甲、西甲及法甲周五同日開賽，周末主要聯賽進入密集賽程。','Guardian賽程確認，9月4日有Ipswich對Liverpool、Stuttgart對Cologne、Genoa對Como、Real Betis對Real Madrid、PSG對Monaco等賽事。','歐洲五大聯賽9月4日進入密集比賽日。英超由Ipswich主場迎戰Liverpool，德甲Stuttgart對Cologne，意甲Genoa對Como；西甲焦點為Real Betis對Real Madrid，法甲則有Lyon對Auxerre及PSG對Monaco。\n\n周末其後還有Newcastle對Bournemouth、Arsenal對Chelsea，以及更多西甲、意甲、德甲與法甲賽事。對有歐洲賽任務的球隊而言，今輪陣容選擇亦會反映之後Champions League與Europa League的輪換部署。','歐洲主要聯賽與歐洲賽程逐步重疊，傷兵、輪換和體能開始成為新季的重要變數。','多場跨聯賽焦點集中同一晚，直接影響各國榜首及歐戰球隊備戰。','留意今晚賽果、傷兵名單、紅黃牌停賽及下周歐洲賽正選安排。','The Guardian','https://www.theguardian.com/football/fixtures/2026/Sep/03','9月4日08:00 HKT前核實'))
N.append(story('mu-women-friday-fixture-20260904-0800',['manchester-united','football'],'Manchester United｜Women／WSL','Manchester United Women今晚作客London City Lionesses　WSL周五開賽','United女隊今晚出戰新一輪WSL，屬球會本周第一場正式比賽；男隊周日則作客Everton。','Guardian賽程顯示Manchester United Women將於9月4日作客London City Lionesses，男子一隊則於9月6日英超作客Everton。','Manchester United Women將於9月4日出戰Women’s Super League，作客London City Lionesses，成為球會本周末最先進行的正式賽事。女隊需要在新季早段保持積分節奏，同時管理國際賽及之後盃賽帶來的輪換。\n\n男子一隊則會在9月6日英超作客Everton。兩支一隊在同一周末都有聯賽任務，球會的官方傷兵、正選及賽前記者會資訊會在今日至周末期間陸續更新。','Manchester United網站專版同時追蹤男子一隊、女隊、青年隊及球會重要人事消息。','女隊今晚有實際賽事，男隊亦即將出戰Everton，屬當前球會最直接的賽程資訊。','留意女隊正選及賽果、男子一隊賽前傷兵、Carrick記者會及Everton作客名單。','The Guardian','https://www.theguardian.com/football/fixtures/2026/Sep/03','9月4日08:00 HKT前核實'))

p=DATA/'desk-latest.json'; d=json.loads(p.read_text(encoding='utf-8'))
d['date']=DATE; d['generatedAt']=GEN; d['mode']='ROLLING_DESK_LATEST'; d['editorialStandardVersion']=3; d['contentVersion']=3
desks=d.setdefault('desks',{})
for slug in FLOORS: desks.setdefault(slug,[])
for s in N:
 for slug in s['deskSlugs']:
  if slug in desks:
   desks[slug]=[x for x in desks[slug] if x.get('id')!=s['id'] and x.get('title')!=s['title']]
   desks[slug].insert(0,deepcopy(s))
# id dedupe and status
for slug,arr in desks.items():
 seen=set(); out=[]
 for x in arr:
  if not isinstance(x,dict) or not x.get('id') or x['id'] in seen: continue
  seen.add(x['id']); x['status']='LATEST'; x.setdefault('deskSlugs',[slug]);
  if slug not in x['deskSlugs']: x['deskSlugs'].append(slug)
  out.append(x)
 desks[slug]=out
for slug,minn in FLOORS.items():
 if len(desks.get(slug,[]))<minn: raise SystemExit(f'DEPTH FAIL {slug} {len(desks.get(slug,[]))}<{minn}')
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
# homepage: fresh priority + diverse retained current stories
pool=[]; seen=set()
for s in N:
 if s['id'] not in seen: pool.append(deepcopy(s)); seen.add(s['id'])
for slug in ['hong-kong','manga-anime','manchester-united','japan','world','asia','market-economy','ai-tech','football']:
 for s in desks[slug]:
  if s.get('id') not in seen:
   pool.append(deepcopy(s)); seen.add(s.get('id'))
  if len(pool)>=40: break
 if len(pool)>=40: break
# top five deliberately cross-desk
wanted=['world-us-birthright-injunction-20260904-0800','asia-taiwan-extra-defence-20260904-0800','japan-oil-cartel-trial-20260904-0800','market-oil-six-week-high-20260904-0800','tech-nvidia-huggingface-acquisition-20260904-0800']
byid={s['id']:s for s in pool}; articles=[deepcopy(byid[i]) for i in wanted]
for s in pool:
 if s['id'] not in {x['id'] for x in articles}: articles.append(deepcopy(s))
 if len(articles)>=18: break
old=json.loads((DATA/'latest.json').read_text(encoding='utf-8')); ed=f"{int(old.get('editionNumber','15'))+1:03d}"
sections=[]
for slug,(title,subtitle) in META.items():
 ids=[a['id'] for a in articles if slug in a.get('deskSlugs',[]) or a.get('desk')==slug]
 if ids: sections.append({'slug':slug,'title':title,'subtitle':subtitle,'articleIds':ids})
latest={'editionNumber':ed,'date':DATE,'dateLabel':DATE_LABEL,'tagline':'全球更新 · 08:00 verified · v3長文','editorialStandardVersion':3,'contentVersion':3,'leadId':wanted[0],'topFive':wanted,'articles':articles,'sections':sections}
text=json.dumps(latest,ensure_ascii=False,indent=2)+'\n'; (DATA/'latest.json').write_text(text,encoding='utf-8'); (DATA/f'{DATE}.json').write_text(text,encoding='utf-8')
# topic-more = wider reservoir excluding homepage ids
home={a['id'] for a in articles}; extra=[]; used=set()
for slug in META:
 for s in desks[slug]:
  if s['id'] not in home and s['id'] not in used: extra.append(deepcopy(s)); used.add(s['id'])
tsections=[]
allids={s['id'] for s in extra}
for slug,(title,subtitle) in META.items():
 ids=[s['id'] for s in extra if slug in s.get('deskSlugs',[]) or s.get('desk')==slug]
 tsections.append({'slug':slug,'title':title,'subtitle':subtitle,'articleIds':ids})
topic={'date':DATE,'editorialStandardVersion':3,'contentVersion':3,'articles':extra,'sections':tsections}
tp=DATA/'topic-more'/f'{DATE}.json'; tp.parent.mkdir(parents=True,exist_ok=True); tp.write_text(json.dumps(topic,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
# archive
ap=DATA/'archive.json'; ar=json.loads(ap.read_text(encoding='utf-8')); ents=ar.setdefault('editions',[]); ents[:]=[x for x in ents if x.get('date')!=DATE]
ents.insert(0,{'date':DATE,'shortDate':'04 SEP 2026','headline':'；'.join(byid[i]['title'] for i in wanted[:3]),'topics':[v[0] for v in META.values()],'url':f'editions/{DATE}.html'})
ap.write_text(json.dumps(ar,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
# archived HTML
html=f'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><base href="../"><meta name="theme-color" content="#111111"><title>{DATE}｜每日晨報 Daily Brief</title><link rel="stylesheet" href="assets/css/newspaper.css?v=20260904"><link rel="stylesheet" href="assets/css/extras.css?v=20260904"><link rel="stylesheet" href="assets/css/monitoring.css?v=20260904"></head><body data-edition="{DATE}"><div class="paper"><div class="utility-bar"><span>ARCHIVED EDITION · HONG KONG</span><span>NO. <span data-edition-number>{ed}</span></span></div><header class="masthead"><div class="masthead-side">世界 · 亞洲 · 香港 · 日本<br>財經 · Stock News · AI · Anime · Football</div><div class="brand"><div class="brand-kicker">個 人 化 電 子 報</div><h1>每日晨報</h1><div class="brand-en">DAILY BRIEF</div></div><div class="masthead-side right">全球更新 · 08:00 verified · v3長文<br>ARCHIVED EDITION</div></header><nav class="section-nav"><a href="live.html">Live</a><a href="index.html">頭版</a><a href="world.html">世界</a><a href="asia.html">亞洲</a><a href="hong-kong.html">香港</a><a href="japan.html">日本</a><a href="finance.html">📈 財經</a><a href="stocks.html">📊 Stock News</a><a href="technology.html">AI / 科技</a><a href="manga-anime.html">漫畫 / Anime</a><a href="manchester-united.html">Manchester United</a><a href="football.html">Football</a><a href="archive.html">Archive</a></nav><div class="date-strip"><span data-edition-date>{DATE}</span><span>GLOBAL VERIFIED DAILY</span></div><main><section class="lead-grid"><article class="lead-story" id="lead-story"><p>正在載入日報…</p></article><aside><div class="section-heading"><h2>今日必讀 5 則</h2><span>TOP FIVE</span></div><div class="top-five" id="top-five"></div></aside></section><div id="dynamic-sections"></div><section class="study-desk" id="study-desk"></section><p class="notice">此頁保存 {DATE} 版本；來源內容可能於原網站後續更新。</p></main><footer class="footer"><span>每日晨報 Daily Brief · {DATE}</span><span><a href="stocks.html">Stock News</a> · <a href="archive.html">Archive</a> · <a href="index.html">今日頭版</a></span></footer></div><script src="assets/js/newspaper.js?v=20260904" defer></script><script src="assets/js/daily-extras.js?v=20260904" defer></script><script src="assets/js/vocab-copy.js?v=20260904" defer></script><script src="assets/js/system-panel.js?v=20260904" defer></script></body></html>'''
ep=ROOT/'editions'/f'{DATE}.html'; ep.write_text(html,encoding='utf-8')
# live daily baseline
lp=DATA/'live.json'; live=json.loads(lp.read_text(encoding='utf-8')) if lp.exists() else {}
live.update({'mode':'DAILY_BASELINE','date':DATE,'editorialStandardVersion':3,'contentVersion':3,'lastUpdated':GEN,'lastUpdatedLabel':'2026年9月4日 08:00 HKT','nextUpdateLabel':'下一輪預定 09:00 HKT','windowLabel':'08:00 Daily Edition','newCount':0,'updatedCount':0,'developingCount':0,'items':[]})
live['coverage']={'status':'DAILY_BASELINE','checkedAt':GEN,'deskLatestStoryCounts':{k:len(v) for k,v in desks.items()},'deskLatestDepthMet':all(len(desks[k])>=FLOORS[k] for k in FLOORS),'qaNote':'08:00 Daily Edition baseline.'}
lp.write_text(json.dumps(live,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
# user hard contract QA
for slug,minn in FLOORS.items():
 n=len(desks[slug]); print(slug,n); assert n>=minn
assert len(desks['japan'])>=8
print('PUBLISHED',DATE,'EDITION',ed,'HOME',len(articles),'TOPIC_MORE',len(extra))
