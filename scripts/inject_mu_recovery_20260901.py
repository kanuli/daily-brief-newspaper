#!/usr/bin/env python3
import json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=ROOT/'data'/'desk-latest.json'
d=json.loads(p.read_text(encoding='utf-8'))
stories=[
{
'id':'mu-dan-gore-luton-loan-20260831-2100','desk':'manchester-united','status':'LATEST','deskSlugs':['manchester-united','football'],'section':'Manchester United｜外借／球員發展','sectionLabel':'Manchester United','mediaLabel':'Manchester United',
'title':'Dan Gore外借Luton至季尾　曼聯中場青訓再赴League One累積比賽時間','dek':'曼聯確認21歲中場Dan Gore外借Luton Town至2026/27球季結束；Luton方面指交易設有有條件買斷選項。','summary':'Dan Gore完成由Manchester United外借Luton Town的交易，將在Jack Wilshere麾下踢完整季League One；這是曼聯轉會窗末段最新一宗已確認球員流動。','body':'Manchester United 8月31日確認，中場青訓Dan Gore同意外借Luton Town至2026/27球季結束，相關註冊程序完成後即可代表新球會上陣。Gore曾為曼聯一隊在聯賽盃及Premier League上陣，之後先後到Port Vale及Rotherham累積英格蘭足球聯賽經驗。\n\nLuton方面亦確認今次為整季外借，並表示交易設有有條件買斷選項。領隊Jack Wilshere稱讚Gore的對抗、持球推進及比賽個性，期望他增加中場強度。對曼聯而言，交易重點是讓仍需穩定一隊分鐘的青訓球員在轉會窗關閉前取得固定發展平台。','context':'Gore近年多次外借，上一季在Rotherham累積大量League One經驗；曼聯在一隊中場重建之餘，亦需要為未進入Carrick常規輪換的青訓球員安排比賽時間。','why':'這是一宗已確認而非傳聞的曼聯球員流動，直接影響球員註冊、青訓發展與今季中場深度管理。','watchNext':'留意Luton完成註冊後Gore的首秀、上陣時間與位置，以及有條件買斷條款會否在球季後觸發。','sourceName':'Manchester United／Luton Town','sourceUrl':'https://www.manutd.com/en/news','timeLabel':'8月31日21:00 HKT前核實','sources':[{'name':'Manchester United','url':'https://www.manutd.com/en/news'},{'name':'Luton Town via CitiBlog','url':'https://citiblog.co.uk/2026/08/31/luton-announce-signing-of-dan-gore-on-loan-from-manchester-united/'}],'image':None
},
{
'id':'mu-jayce-fitzgerald-rotherham-loan-20260831-1900','desk':'manchester-united','status':'LATEST','deskSlugs':['manchester-united','football'],'section':'Manchester United｜外借／青訓','sectionLabel':'Manchester United','mediaLabel':'Manchester United',
'title':'Jayce Fitzgerald外借Rotherham一季　19歲曼聯青訓中場首次離開奧脫福借用','dek':'Manchester United及Rotherham均確認Fitzgerald完成整季外借；他上季為U21在Premier League 2出場16次。','summary':'19歲中場Jayce Fitzgerald由Manchester United外借Rotherham United至球季結束，成為轉會窗末段另一宗已確認青訓安排。','body':'Manchester United確認，19歲中場Jayce Fitzgerald已外借Rotherham United至2026/27球季結束。Fitzgerald自幼加入曼聯青訓，上季為U21在Premier League 2出場16次，亦曾在一隊比賽日名單列後備，但尚未完成正式一隊上陣。\n\nRotherham方面同樣公布交易，這是Fitzgerald首次以外借方式離開Old Trafford。他將在前曼聯青訓球員Alex Bruce執教的球隊爭取成年隊分鐘，而前曼聯助教Steve McClaren目前亦在Rotherham擔任足球主管。交易在轉會窗關閉前完成，令Fitzgerald可立即加入新隊比賽計劃。','context':'曼聯近年持續利用EFL外借為青訓球員提供成年隊經驗；Fitzgerald此前主要在U18及U21比賽，今次是他首次完整球季外借。','why':'這宗已確認外借直接影響曼聯Academy人員配置，也提供觀察高潛力中場由青年賽事過渡成年職業足球的實際樣本。','watchNext':'留意Fitzgerald能否進入Rotherham正選輪換、首場出賽時間，以及曼聯是否在轉會窗最後階段再安排其他青訓球員外借。','sourceName':'Manchester United／Rotherham United','sourceUrl':'https://www.manutd.com/en/news','timeLabel':'8月31日19:00 HKT前核實','sources':[{'name':'Manchester United','url':'https://www.manutd.com/en/news'},{'name':'Rotherham United announcement relayed by FootballTransfers','url':'https://www.fussballtransfers.com/a5866987898097903293-united-verleiht-fitzgerald'}],'image':None
},
{
'id':'mu-u21-leicester-4-1-20260831-2300','desk':'manchester-united','status':'LATEST','deskSlugs':['manchester-united','football'],'section':'Manchester United｜Academy／Premier League 2','sectionLabel':'Manchester United','mediaLabel':'Manchester United',
'title':'曼聯U21以4比1擊敗Leicester　Shea Lacey梅開二度、開季PL2兩戰全勝','dek':'Lacey上半場兩度建功，Amir Ibragimov及JJ Gabriel亦有入球，United U21延續開季強勢。','summary':'Manchester United U21在Premier League 2主場4比1擊敗Leicester City U21，Shea Lacey攻入兩球，球隊取得聯賽兩連勝。','body':'Manchester United官方賽後報道確認，U21在8月31日的Premier League 2賽事以4比1擊敗Leicester City U21。Shea Lacey在上半場先後射入兩球，Amir Ibragimov在半場前擴大優勢，後備上陣的JJ Gabriel在尾段再下一城。\n\n這場勝利令Adam Lawrence帶領的U21開季聯賽兩戰全勝。Lacey今場由一隊比賽日陣容回到U21並立即成為進攻焦點，而Gabriel、Ibragimov等年輕球員亦繼續獲得高強度比賽時間。Academy表現本身不等同一隊即時補強，但會影響Carrick之後對盃賽及一隊後備席的人選。','context':'曼聯U21上一輪以5比0擊敗Ipswich，今場再贏Leicester，年輕進攻球員在新季開始階段保持高輸出。','why':'這是與一隊5比2擊敗Ipswich不同的獨立球會事件，反映Academy球員狀態與一隊潛在後備資源。','watchNext':'留意Lacey及Gabriel會否在國際賽期後再次進入一隊名單，以及U21下場對Manchester City的陣容安排。','sourceName':'Manchester United','sourceUrl':'https://www.manutd.com/en/news/report-man-utd-u21s-4-leicester-1-31-august-2026','timeLabel':'8月31日23:00 HKT前核實','sources':[{'name':'Manchester United','url':'https://www.manutd.com/en/news/report-man-utd-u21s-4-leicester-1-31-august-2026'},{'name':'Man United Daily','url':'https://manuniteddaily.com/youth/shea-lacey-hits-a-double-and-jj-gabriel-on-target-as-man-utd-u21s-crush-leicester-4-1'}],'image':None
}
]
rows=d['desks'].setdefault('manchester-united',[])
existing={x.get('id') for x in rows}
for s in stories:
    if s['id'] not in existing: rows.append(s)
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('MU recovery injected',len(stories))
