#!/usr/bin/env python3
"""Traditional-Chinese localization for Cantonese TTS.

Display copy may keep official English/romanized names, but the speech script
uses established Hong Kong Traditional-Chinese names wherever possible.
Taiwan Traditional-Chinese names are used only when Hong Kong has no stable
local form. Residual Latin text is audited by desk so CosyVoice is not asked to
guess a different language/accent mid-sentence.
"""
from __future__ import annotations

import re

REPLACEMENTS = [
    # World / Asia — Hong Kong forms first
    ("Long Island Expressway", "長島高速公路"),
    ("G20 Common Framework", "二十國集團共同框架"),
    ("New Money Warrant", "新資金認股權證"),
    ("Common Framework", "共同框架"),
    ("Associated Press", "美聯社"),
    ("Kryvyi Rih", "克里維里赫"),
    ("Mark Carney", "卡尼"),
    ("Ocean Winner", "海洋勝利號"),
    ("Long Island", "長島"),
    ("Atlantic Beach", "大西洋海灘"),
    ("Sandy Hook", "桑迪胡克"),
    ("Alex Jones", "亞歷斯鍾斯"),
    ("Connecticut", "康涅狄格州"),
    ("Delaware", "特拉華州"),
    ("Queens", "皇后區"),
    ("Dover", "多佛"),
    ("Eurobond", "國際債券"),
    ("USMCA", "美墨加貿易協定"),
    ("NASA", "美國太空總署"),
    ("Reuters", "路透社"),
    ("The Guardian", "英國衛報"),
    ("BBC", "英國廣播公司"),
    ("CNN", "美國有線新聞網絡"),
    ("ABC", "美國廣播公司"),
    ("CBS", "哥倫比亞廣播公司"),
    ("NBC", "全國廣播公司"),
    ("UN", "聯合國"),
    ("WHO", "世界衛生組織"),
    ("WTO", "世界貿易組織"),
    ("IMF", "國際貨幣基金組織"),
    ("NATO", "北約"),
    ("EU", "歐盟"),
    ("ASEAN", "東盟"),
    ("APEC", "亞太經合組織"),

    # Hong Kong / compact identifiers that must be resolved before number handling
    ("MU88", "都大八十八學生宿舍"),

    # Finance / economics
    ("£51m", "五千一百萬英鎊"),
    ("Federal Reserve", "美國聯儲局"),
    ("Fed", "美國聯儲局"),
    ("FOMC", "美國聯儲局公開市場委員會"),
    ("ECB", "歐洲中央銀行"),
    ("BOJ", "日本銀行"),
    ("HKMA", "香港金融管理局"),
    ("GDP", "本地生產總值"),
    ("CPI", "消費物價指數"),
    ("PPI", "生產物價指數"),
    ("IPO", "首次公開招股"),
    ("ETF", "交易所買賣基金"),
    ("SEC", "美國證券交易委員會"),
    ("FDA", "美國食品藥物管理局"),

    # Technology / AI
    ("NVIDIA", "輝達"),
    ("Nvidia", "輝達"),
    ("Microsoft", "微軟"),
    ("Apple", "蘋果公司"),
    ("Amazon", "亞馬遜"),
    ("Meta", "臉書母公司"),
    ("OpenAI", "開放人工智能公司"),
    ("ChatGPT", "人工智能聊天機械人"),
    ("Google", "谷歌"),
    ("Android", "安卓"),
    ("iPhone", "蘋果手機"),
    ("AI", "人工智能"),
    ("GPU", "圖像處理器"),
    ("CPU", "中央處理器"),
    ("API", "應用程式介面"),
    ("cloud", "雲端"),
    ("Cloud", "雲端"),

    # Manga / anime — visible copy and speech both use Traditional Chinese
    ("ONE PIECE FILM GOD VALLEY", "海賊王劇場版：神之谷"),
    ("ONE PIECE FILM BAAD", "海賊王劇場版：巴德（暫譯）"),
    ("ONE PIECE FILM RED", "海賊王劇場版：紅髮歌姬"),
    ("ONE PIECE DAY", "海賊王日"),
    ("ONE PIECE", "海賊王"),

    # Japan football — Hong Kong sports-media naming
    ("JEF United Chiba", "千葉市原"),
    ("JEF Chiba", "千葉市原"),
    ("Kawasaki Frontale", "川崎前鋒"),
    ("Kashiwa Reysol", "柏雷素爾"),
    ("V-Varen Nagasaki", "長崎成功丸"),
    ("V Varen Nagasaki", "長崎成功丸"),
    ("FC Tokyo", "東京足球會"),
    ("FC東京", "東京足球會"),
    ("J.League", "日本職業足球聯賽"),
    ("J League", "日本職業足球聯賽"),
    ("J1", "日職聯賽"),

    # English / European football — Hong Kong naming
    ("Manchester United", "曼聯"),
    ("Manchester City", "曼城"),
    ("Hull City", "侯城"),
    ("Jack Clarke", "積克奇勒"),
    ("Arsenal", "阿仙奴"),
    ("Liverpool", "利物浦"),
    ("Chelsea", "車路士"),
    ("Tottenham Hotspur", "熱刺"),
    ("Tottenham", "熱刺"),
    ("Spurs", "熱刺"),
    ("Newcastle United", "紐卡素"),
    ("Newcastle", "紐卡素"),
    ("Aston Villa", "阿士東維拉"),
    ("Brighton", "白禮頓"),
    ("Bournemouth", "般尼茅夫"),
    ("Brentford", "賓福特"),
    ("Fulham", "富咸"),
    ("Everton", "愛華頓"),
    ("Crystal Palace", "水晶宮"),
    ("Ipswich Town", "葉士域治"),
    ("Sunderland", "新特蘭"),
    ("Nottingham Forest", "諾定咸森林"),
    ("Leeds United", "列斯聯"),
    ("Leeds", "列斯聯"),
    ("Coventry City", "高雲地利"),
    ("AC Milan", "米蘭足球會"),
    ("Barcelona", "巴塞隆拿"),
    ("Real Madrid", "皇家馬德里"),
    ("Bayern Munich", "拜仁慕尼黑"),
    ("Paris Saint-Germain", "巴黎聖日耳門"),
    ("PSG", "巴黎聖日耳門"),
    ("Champions League", "歐洲聯賽冠軍盃"),
    ("Premier League", "英格蘭超級聯賽"),
    ("La Liga", "西班牙甲組聯賽"),
    ("Serie A", "意大利甲組聯賽"),
    ("Bundesliga", "德國甲組聯賽"),
    ("Ligue 1", "法國甲組聯賽"),
    ("UEFA", "歐洲足協"),
    ("FIFA", "國際足協"),
    ("FT", "完場"),

    # Common editorial/source words
    ("Official", "官方"),
    ("official", "官方"),
    ("Breaking News", "突發新聞"),
    ("Live", "即時"),
    ("Update", "更新"),
]

SHORT_ACRONYMS = {
    "US": "美國",
    "USA": "美國",
    "UK": "英國",
    "HK": "香港",
    "HKT": "香港時間",
    "PRC": "中國",
    "UAE": "阿聯酋",
    "EV": "電動車",
    "EVs": "電動車",
    "PC": "個人電腦",
    "TV": "電視",
    "PV": "宣傳片",
}

# Important: only ASCII boundaries. Using \w here incorrectly treats adjacent
# Chinese characters as word characters and hides embedded English such as
# 「美元Eurobond」 or 「FC Tokyo在主場」 from the audit.
LATIN_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9.+&'’/-]*)(?![A-Za-z0-9])")


def _phrase_replace(text: str, source: str, target: str) -> str:
    if source.isascii() and any(ch.isalpha() for ch in source):
        pattern = re.compile(r"(?<![A-Za-z0-9])" + re.escape(source) + r"(?![A-Za-z0-9])", re.IGNORECASE)
        return pattern.sub(target, text)
    return text.replace(source, target)


def localize(text: str) -> str:
    out = str(text or "")
    for source, target in sorted(REPLACEMENTS, key=lambda item: len(item[0]), reverse=True):
        out = _phrase_replace(out, source, target)
    for source, target in sorted(SHORT_ACRONYMS.items(), key=lambda item: len(item[0]), reverse=True):
        out = re.sub(r"(?<![A-Za-z0-9])" + re.escape(source) + r"(?![A-Za-z0-9])", target, out)
    return out


def residual_latin_tokens(text: str) -> list[str]:
    localized = localize(text)
    return sorted({m.group(1) for m in LATIN_TOKEN_RE.finditer(localized)}, key=str.lower)


def has_residual_latin(text: str) -> bool:
    return bool(residual_latin_tokens(text))
