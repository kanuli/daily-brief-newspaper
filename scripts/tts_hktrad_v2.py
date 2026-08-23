#!/usr/bin/env python3
"""Speech-only Traditional-Chinese localization used by production Cantonese TTS."""
import re
import tts_hktrad as base

# Specific/long phrases first.  Display copy is untouched; only speech text uses
# these replacements.  Hong Kong newsroom / sports usage is preferred, with a
# Traditional-Chinese phonetic form when a stable local form is unavailable.
OVERRIDES = [
    # World / Asia
    ("Rufin Benam Beltoungou", "魯芬貝南貝爾通古"),
    ("Nana-Mambéré", "納納曼貝雷"),
    ("Nana-Mamb", "納納曼貝雷"),
    ("Scott Bessent", "貝森特"),
    ("Masoud Pezeshkian", "佩澤希齊揚"),
    ("Zelenskyy", "澤連斯基"),
    ("Pezeshkian", "佩澤希齊揚"),
    ("Beltoungou", "貝爾通古"),
    ("Zamboye", "贊博耶"),
    ("Bessent", "貝森特"),
    ("Tanintharyi", "德林達依"),
    ("Paradip", "帕拉迪普"),
    ("Odisha", "奧里薩邦"),
    ("Rufin", "魯芬"),
    ("Benam", "貝南"),
    ("Dawei", "土瓦"),
    ("Jones", "鍾斯"),
    ("Scott", "斯科特"),
    ("Masoud", "馬蘇德"),

    # Hong Kong
    ("material risk takers", "重大風險承擔人員"),
    ("Financial Times", "英國金融時報"),
    ("HSBC", "滙豐"),
    ("MU88", "都大八十八學生宿舍"),

    # Japan / public safety
    ("TV Asahi", "朝日電視台"),
    ("Level 4", "警戒級別四"),
    ("M5.9", "黎克特制五點九級"),
    ("Bastion", "堡壘岸防導彈系統"),
    ("Asahi", "朝日電視台"),
    ("JST", "日本時間"),
    ("Level", "警戒級別"),

    # Finance / markets / stock
    ("Jackson Hole", "傑克遜霍爾"),
    ("Equatorial Margin", "赤道邊緣海域"),
    ("Keta Basin", "凱塔盆地"),
    ("READ-THROUGH", "延伸解讀"),
    ("ex-China", "中國以外"),
    ("Petrobras", "巴西石油公司"),
    ("Bitcoin", "比特幣"),
    ("Brent", "布蘭特"),
    ("NVDA", "英偉達"),
    ("PCE", "個人消費開支物價指數"),
    ("EMXC", "新興市場除中國基金"),
    ("EWY", "韓國交易所買賣基金"),
    ("KOSPI", "韓國綜合股價指數"),
    ("VT", "全球股票基金"),
    ("EM", "新興市場"),
    ("beta", "貝塔值"),

    # NVIDIA / AI / technology
    ("Cloverleaf Infrastructure", "克洛弗利夫基建公司"),
    ("World Athletics", "世界田徑總會"),
    ("Petra Tschudin", "佩特拉楚丁"),
    ("pitch deck", "推介簡報"),
    ("Digital Markets Act", "數碼市場法"),
    ("In-App Purchase", "應用程式內購"),
    ("In-App", "應用程式內"),
    ("App Store", "應用程式商店"),
    ("SK Hynix", "愛思開海力士"),
    ("Blackwell", "布萊克韋爾"),
    ("Bloomberg", "彭博"),
    ("Cloverleaf", "克洛弗利夫"),
    ("Tschudin", "楚丁"),
    ("Hollywood", "荷里活"),
    ("Honor", "榮耀"),
    ("Alphabet", "谷歌母公司"),
    ("Breakingviews", "路透評論"),
    ("Palantir", "帕蘭泰爾"),
    ("Marvell", "邁威爾"),
    ("Samsung", "三星"),
    ("Hynix", "海力士"),
    ("Oracle", "甲骨文"),
    ("Copilot", "微軟人工智能助手"),
    ("Azure", "微軟雲端平台"),
    ("Gemini", "谷歌雙子星人工智能"),
    ("TSMC", "台積電"),
    ("CoWoS", "晶圓上封裝技術"),
    ("AAPL", "蘋果公司"),
    ("GOOG", "谷歌"),
    ("DRAM", "動態隨機存取記憶體"),
    ("HBM", "高頻寬記憶體"),
    ("TPU", "張量處理器"),
    ("RPO", "剩餘履約責任"),
    ("IAP", "應用程式內購"),
    ("DSX", "數據中心設計平台"),
    ("Grace", "格雷斯"),
    ("Rubin", "魯賓"),
    ("Vera", "維拉"),
    ("Petra", "佩特拉"),
    ("Infrastructure", "基建"),
    ("Athletics", "田徑"),
    ("Electronics", "電子"),
    ("commercial", "商業"),
    ("government", "政府"),
    ("Developer", "開發者"),
    ("Technology", "科技"),
    ("Commission", "委員會"),
    ("Services", "服務"),
    ("Purchase", "購買"),
    ("Markets", "市場"),
    ("Digital", "數碼"),
    ("Search", "搜尋"),
    ("Store", "商店"),
    ("Core", "核心"),
    ("Fee", "費用"),
    ("Act", "法案"),
    ("App", "應用程式"),
    ("pitch", "推介"),
    ("deck", "簡報"),
    ("World", "世界"),
    ("SK", "愛思開"),
    # Base table previously used a Taiwan-first NVIDIA form; production speech
    # uses the common Hong Kong form instead.
    ("輝達", "英偉達"),

    # Manga / anime
    ("Disney Twisted-Wonderland", "迪士尼扭曲仙境"),
    ("Fate/strange Fake", "命運奇異贗品"),
    ("Teaser Visual", "預告視覺圖"),
    ("Twisted-Wonderland", "扭曲仙境"),
    ("Disney+", "迪士尼串流平台"),
    ("Aniplex", "安尼普"),
    ("SideM", "偶像大師男性系列"),
    ("Disney", "迪士尼"),
    ("Nagano", "長野"),
    ("Oricon", "日本公信榜"),
    ("Teaser", "預告"),
    ("Visual", "視覺圖"),
    ("Fate", "命運"),
    ("Fake", "贗品"),
    ("IP", "知識產權"),
    ("VS", "對決"),

    # Manchester United
    ("Konstantinos Tzolakis", "高斯坦天奴祖拉基斯"),
    ("Michael Carrick", "卡域克"),
    ("Semi Ajayi", "森美阿積耶"),
    ("Nobel Mendy", "諾貝爾文迪"),
    ("Marcus Rashford", "拉舒福特"),
    ("Andrey Santos", "安德利山度士"),
    ("Youri Tielemans", "泰利文斯"),
    ("Carlos Baleba", "卡路士巴利巴"),
    ("Bruno Fernandes", "般奴費南迪斯"),
    ("Old Trafford", "奧脫福"),
    ("Tielemans", "泰利文斯"),
    ("Rashford", "拉舒福特"),
    ("Fernandes", "費南迪斯"),
    ("Tzolakis", "祖拉基斯"),
    ("Carrick", "卡域克"),
    ("Andrey", "安德利"),
    ("Santos", "山度士"),
    ("Baleba", "巴利巴"),
    ("Ajayi", "阿積耶"),
    ("Mendy", "文迪"),
    ("Marcus", "馬古斯"),
    ("Michael", "米高"),
    ("Nobel", "諾貝爾"),
    ("Semi", "森美"),
    ("Bruno", "般奴"),
    ("Carlos", "卡路士"),
    ("Ipswich", "葉士域治"),
    ("United", "曼聯"),
    ("Hull", "侯城"),

    # General football
    ("AFC Champions League Elite", "亞洲聯賽冠軍盃精英賽"),
    ("Mamadou Sangaré", "馬馬杜辛加利"),
    ("Mamadou Sangar", "馬馬杜辛加利"),
    ("Keane Lewis-Potter", "堅尼路易斯樸達"),
    ("Vitaly Janelt", "維塔利亞內特"),
    ("Michael Kayode", "米高卡約迪"),
    ("Martin Ødegaard", "奧迪加特"),
    ("Bukayo Saka", "布卡約沙卡"),
    ("Championship", "英格蘭冠軍聯賽"),
    ("Ødegaard", "奧迪加特"),
    ("Saka", "沙卡"),
    ("Mehdi Taremi", "美迪泰利美"),
    ("João Pedro", "祖奧柏度"),
    ("Xabi Alonso", "沙比阿朗素"),
    ("Club World Cup", "世界冠軍球會盃"),
    ("Inter Milan", "國際米蘭"),
    ("Kai Havertz", "夏維斯"),
    ("Ezri Konsa", "干沙"),
    ("Al Wasl", "艾華斯爾"),
    ("Olympiacos", "奧林比亞高斯"),
    ("Coventry", "高雲地利"),
    ("Lewis-Potter", "路易斯樸達"),
    ("Janelt", "亞內特"),
    ("Kayode", "卡約迪"),
    ("Sangar", "辛加利"),
    ("Havertz", "夏維斯"),
    ("Konsa", "干沙"),
    ("Taremi", "泰利美"),
    ("Frontale", "前鋒"),
    ("Reysol", "雷素爾"),
    ("Porto", "波圖"),
    ("Villa", "維拉"),
    ("AFC", "亞洲足協"),
    ("Elite", "精英賽"),
    ("Club", "球會"),
    ("Cup", "盃"),
    ("Milan", "米蘭"),
    ("Al", "艾爾"),

    # Common remaining source/editorial tokens
    ("AP", "美聯社"),
    ("warrant", "認股權證"),
]


def _replace(text, source, target):
    return re.sub(
        r"(?<![A-Za-z0-9])" + re.escape(source) + r"(?![A-Za-z0-9])",
        target,
        text,
        flags=re.IGNORECASE,
    )


def localize(text):
    out = base.localize(text)
    for source, target in sorted(OVERRIDES, key=lambda item: len(item[0]), reverse=True):
        out = _replace(out, source, target)
    return out


def residual_latin_tokens(text):
    localized = localize(text)
    return sorted({m.group(1) for m in base.LATIN_TOKEN_RE.finditer(localized)}, key=str.lower)


def has_residual_latin(text):
    return bool(residual_latin_tokens(text))
