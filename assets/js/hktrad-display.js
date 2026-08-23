(() => {
  "use strict";

  // Visible-news localization only. This never changes URLs, source links,
  // program instructions, TTS control text, or metadata.
  const REPLACEMENTS = [
    // World / Asia
    ["Rufin Benam Beltoungou", "魯芬貝南貝爾通古"], ["Long Island Expressway", "長島高速公路"],
    ["G20 Common Framework", "二十國集團共同框架"], ["New Money Warrant", "新資金認股權證"],
    ["Common Framework", "共同框架"], ["Associated Press", "美聯社"], ["Kryvyi Rih", "克里維里赫"],
    ["Masoud Pezeshkian", "佩澤希齊揚"], ["Scott Bessent", "貝森特"], ["Mark Carney", "卡尼"],
    ["Ocean Winner", "海洋勝利號"], ["Long Island", "長島"], ["Atlantic Beach", "大西洋海灘"],
    ["Sandy Hook", "桑迪胡克"], ["Alex Jones", "亞歷斯鍾斯"], ["Connecticut", "康涅狄格州"],
    ["Nana-Mambéré", "納納曼貝雷"], ["Nana-Mamb", "納納曼貝雷"], ["Zelenskyy", "澤連斯基"],
    ["Pezeshkian", "佩澤希齊揚"], ["Beltoungou", "貝爾通古"], ["Tanintharyi", "德林達依"],
    ["Paradip", "帕拉迪普"], ["Odisha", "奧里薩邦"], ["Zamboye", "贊博耶"],
    ["Bessent", "貝森特"], ["Rufin", "魯芬"], ["Benam", "貝南"], ["Dawei", "土瓦"],
    ["Delaware", "特拉華州"], ["Queens", "皇后區"], ["Dover", "多佛"], ["Eurobond", "國際債券"],
    ["USMCA", "美墨加貿易協定"], ["NASA", "美國太空總署"], ["Reuters", "路透社"],
    ["The Guardian", "英國衛報"], ["BBC", "英國廣播公司"], ["CNN", "美國有線新聞網絡"],
    ["ABC", "美國廣播公司"], ["CBS", "哥倫比亞廣播公司"], ["NBC", "全國廣播公司"],
    ["NATO", "北約"], ["ASEAN", "東盟"], ["APEC", "亞太經合組織"], ["WHO", "世界衛生組織"],
    ["WTO", "世界貿易組織"], ["IMF", "國際貨幣基金組織"], ["UN", "聯合國"], ["EU", "歐盟"],
    ["Jones", "鍾斯"], ["Scott", "斯科特"], ["Masoud", "馬蘇德"],

    // Hong Kong
    ["material risk takers", "重大風險承擔人員"], ["Financial Times", "英國金融時報"],
    ["HSBC", "滙豐"], ["MU88", "都大八十八學生宿舍"],

    // Japan / public safety
    ["TV Asahi", "朝日電視台"], ["Level 4", "警戒級別四"], ["M5.9", "黎克特制五點九級"],
    ["Bastion", "堡壘岸防導彈系統"], ["Asahi", "朝日電視台"], ["JST", "日本時間"],
    ["Level", "警戒級別"],

    // Finance / markets
    ["Federal Reserve", "美國聯儲局"], ["Jackson Hole", "傑克遜霍爾"],
    ["Equatorial Margin", "赤道邊緣海域"], ["Keta Basin", "凱塔盆地"], ["READ-THROUGH", "延伸解讀"],
    ["ex-China", "中國以外"], ["Petrobras", "巴西石油公司"], ["Bitcoin", "比特幣"],
    ["Brent", "布蘭特"], ["FOMC", "美國聯儲局公開市場委員會"], ["HKMA", "香港金融管理局"],
    ["NVDA", "英偉達"], ["PCE", "個人消費開支物價指數"], ["EMXC", "新興市場除中國基金"],
    ["EWY", "韓國交易所買賣基金"], ["KOSPI", "韓國綜合股價指數"], ["GDP", "本地生產總值"],
    ["CPI", "消費物價指數"], ["PPI", "生產物價指數"], ["IPO", "首次公開招股"],
    ["ETF", "交易所買賣基金"], ["SEC", "美國證券交易委員會"], ["FDA", "美國食品藥物管理局"],
    ["ECB", "歐洲中央銀行"], ["BOJ", "日本銀行"], ["Fed", "美國聯儲局"], ["VT", "全球股票基金"],
    ["EM", "新興市場"], ["beta", "貝塔值"],

    // AI / technology
    ["Cloverleaf Infrastructure", "克洛弗利夫基建公司"], ["World Athletics", "世界田徑總會"],
    ["Petra Tschudin", "佩特拉楚丁"], ["Digital Markets Act", "數碼市場法"],
    ["In-App Purchase", "應用程式內購"], ["In-App", "應用程式內"], ["App Store", "應用程式商店"],
    ["SK Hynix", "愛思開海力士"], ["OpenAI", "開放人工智能公司"], ["ChatGPT", "人工智能聊天機械人"],
    ["Microsoft", "微軟"], ["NVIDIA", "英偉達"], ["Nvidia", "英偉達"], ["Apple", "蘋果公司"],
    ["Amazon", "亞馬遜"], ["Alphabet", "谷歌母公司"], ["Google", "谷歌"], ["Meta", "臉書母公司"],
    ["Android", "安卓"], ["iPhone", "蘋果手機"], ["Blackwell", "布萊克韋爾"], ["Bloomberg", "彭博"],
    ["Cloverleaf", "克洛弗利夫"], ["Tschudin", "楚丁"], ["Hollywood", "荷里活"], ["Honor", "榮耀"],
    ["Breakingviews", "路透評論"], ["Palantir", "帕蘭泰爾"], ["Marvell", "邁威爾"], ["Samsung", "三星"],
    ["Hynix", "海力士"], ["Oracle", "甲骨文"], ["Copilot", "微軟人工智能助手"],
    ["Azure", "微軟雲端平台"], ["Gemini", "谷歌雙子星人工智能"], ["TSMC", "台積電"],
    ["CoWoS", "晶圓上封裝技術"], ["AAPL", "蘋果公司"], ["GOOG", "谷歌"],
    ["DRAM", "動態隨機存取記憶體"], ["HBM", "高頻寬記憶體"], ["TPU", "張量處理器"],
    ["RPO", "剩餘履約責任"], ["IAP", "應用程式內購"], ["DSX", "數據中心設計平台"],
    ["GPU", "圖像處理器"], ["CPU", "中央處理器"], ["API", "應用程式介面"],
    ["Grace", "格雷斯"], ["Rubin", "魯賓"], ["Vera", "維拉"], ["Petra", "佩特拉"],
    ["Infrastructure", "基建"], ["Athletics", "田徑"], ["Electronics", "電子"], ["commercial", "商業"],
    ["government", "政府"], ["Developer", "開發者"], ["Technology", "科技"], ["Commission", "委員會"],
    ["Services", "服務"], ["Purchase", "購買"], ["Markets", "市場"], ["Digital", "數碼"],
    ["Search", "搜尋"], ["Store", "商店"], ["Core", "核心"], ["Fee", "費用"], ["Act", "法案"],
    ["App", "應用程式"], ["pitch deck", "推介簡報"], ["pitch", "推介"], ["deck", "簡報"],
    ["cloud", "雲端"], ["AI", "人工智能"], ["World", "世界"], ["SK", "愛思開"], ["輝達", "英偉達"],

    // Manga / anime
    ["Disney Twisted-Wonderland", "迪士尼扭曲仙境"], ["Fate/strange Fake", "命運奇異贗品"],
    ["Teaser Visual", "預告視覺圖"], ["Twisted-Wonderland", "扭曲仙境"], ["Disney+", "迪士尼串流平台"],
    ["Aniplex", "安尼普"], ["SideM", "偶像大師男性系列"], ["Disney", "迪士尼"], ["Nagano", "長野"],
    ["Oricon", "日本公信榜"], ["Teaser", "預告"], ["Visual", "視覺圖"], ["Fate", "命運"],
    ["Fake", "贗品"], ["Anime", "動畫"], ["IP", "知識產權"], ["VS", "對決"],

    // Japan football
    ["JEF United Chiba", "千葉市原"], ["JEF Chiba", "千葉市原"], ["Kawasaki Frontale", "川崎前鋒"],
    ["Kashiwa Reysol", "柏雷素爾"], ["V-Varen Nagasaki", "長崎成功丸"], ["V Varen Nagasaki", "長崎成功丸"],
    ["FC Tokyo", "東京足球會"], ["FC東京", "東京足球會"], ["J.League", "日本職業足球聯賽"],
    ["J League", "日本職業足球聯賽"], ["J1", "日職聯賽"],

    // Manchester United / English football
    ["Konstantinos Tzolakis", "高斯坦天奴祖拉基斯"], ["Michael Carrick", "卡域克"],
    ["Semi Ajayi", "森美阿積耶"], ["Nobel Mendy", "諾貝爾文迪"], ["Marcus Rashford", "拉舒福特"],
    ["Andrey Santos", "安德利山度士"], ["Youri Tielemans", "泰利文斯"], ["Carlos Baleba", "卡路士巴利巴"],
    ["Bruno Fernandes", "般奴費南迪斯"], ["Old Trafford", "奧脫福"], ["Manchester United", "曼聯"],
    ["Manchester City", "曼城"], ["Hull City", "侯城"], ["Newcastle United", "紐卡素"],
    ["Aston Villa", "阿士東維拉"], ["Crystal Palace", "水晶宮"], ["Ipswich Town", "葉士域治"],
    ["Nottingham Forest", "諾定咸森林"], ["Leeds United", "列斯聯"], ["Coventry City", "高雲地利"],
    ["Tottenham Hotspur", "熱刺"], ["Paris Saint-Germain", "巴黎聖日耳門"], ["Real Madrid", "皇家馬德里"],
    ["Bayern Munich", "拜仁慕尼黑"], ["AC Milan", "米蘭足球會"], ["Arsenal", "阿仙奴"],
    ["Liverpool", "利物浦"], ["Chelsea", "車路士"], ["Tottenham", "熱刺"], ["Newcastle", "紐卡素"],
    ["Brighton", "白禮頓"], ["Bournemouth", "般尼茅夫"], ["Brentford", "賓福特"], ["Fulham", "富咸"],
    ["Everton", "愛華頓"], ["Sunderland", "新特蘭"], ["Barcelona", "巴塞隆拿"], ["PSG", "巴黎聖日耳門"],
    ["Tielemans", "泰利文斯"], ["Rashford", "拉舒福特"], ["Fernandes", "費南迪斯"], ["Tzolakis", "祖拉基斯"],
    ["Carrick", "卡域克"], ["Andrey", "安德利"], ["Santos", "山度士"], ["Baleba", "巴利巴"],
    ["Ajayi", "阿積耶"], ["Mendy", "文迪"], ["Marcus", "馬古斯"], ["Michael", "米高"],
    ["Nobel", "諾貝爾"], ["Semi", "森美"], ["Bruno", "般奴"], ["Carlos", "卡路士"],
    ["Ipswich", "葉士域治"], ["United", "曼聯"], ["Hull", "侯城"],

    // General football
    ["AFC Champions League Elite", "亞洲聯賽冠軍盃精英賽"], ["Champions League", "歐洲聯賽冠軍盃"],
    ["Premier League", "英格蘭超級聯賽"], ["Club World Cup", "世界冠軍球會盃"],
    ["Mamadou Sangaré", "馬馬杜辛加利"], ["Mamadou Sangar", "馬馬杜辛加利"],
    ["Keane Lewis-Potter", "堅尼路易斯樸達"], ["Vitaly Janelt", "維塔利亞內特"],
    ["Michael Kayode", "米高卡約迪"], ["Martin Ødegaard", "奧迪加特"], ["Bukayo Saka", "布卡約沙卡"],
    ["Championship", "英格蘭冠軍聯賽"], ["Ødegaard", "奧迪加特"], ["Saka", "沙卡"],
    ["Mehdi Taremi", "美迪泰利美"], ["João Pedro", "祖奧柏度"], ["Xabi Alonso", "沙比阿朗素"],
    ["Inter Milan", "國際米蘭"], ["Kai Havertz", "夏維斯"], ["Ezri Konsa", "干沙"],
    ["Al Wasl", "艾華斯爾"], ["Olympiacos", "奧林比亞高斯"], ["Coventry", "高雲地利"],
    ["Lewis-Potter", "路易斯樸達"], ["Janelt", "亞內特"], ["Kayode", "卡約迪"], ["Sangar", "辛加利"],
    ["Havertz", "夏維斯"], ["Konsa", "干沙"], ["Taremi", "泰利美"], ["Frontale", "前鋒"],
    ["Reysol", "雷素爾"], ["Porto", "波圖"], ["Villa", "維拉"], ["La Liga", "西班牙甲組聯賽"],
    ["Serie A", "意大利甲組聯賽"], ["Bundesliga", "德國甲組聯賽"], ["Ligue 1", "法國甲組聯賽"],
    ["UEFA", "歐洲足協"], ["FIFA", "國際足協"], ["AFC", "亞洲足協"], ["Elite", "精英賽"],
    ["Club", "球會"], ["Cup", "盃"], ["Milan", "米蘭"], ["Al", "艾爾"], ["FT", "完場"],

    // Generic editorial/UI words when they appear inside visible news copy
    ["Breaking News", "突發新聞"], ["Stock News", "股票新聞"], ["Football", "足球"],
    ["Official", "官方"], ["LATEST", "最新"], ["UPDATED", "已更新"], ["DEVELOPING", "發展中"],
    ["UPDATE", "更新"], ["Update", "更新"], ["LIVE", "即時"], ["Live", "即時"],
    ["AP", "美聯社"], ["warrant", "認股權證"]
  ];

  const SHORT = { US: "美國", USA: "美國", UK: "英國", HK: "香港", HKT: "香港時間", PRC: "中國", UAE: "阿聯酋", EV: "電動車", EVs: "電動車", PC: "個人電腦", TV: "電視", PV: "宣傳片" };
  const SKIP = "a,script,style,code,pre,.source-link,.topic-sources,.story-meta,[data-no-hktrad-display]";

  const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const phraseRules = [...REPLACEMENTS]
    .sort((a, b) => b[0].length - a[0].length)
    .map(([source, target]) => [new RegExp(`(?<![A-Za-z0-9])${escapeRegExp(source)}(?![A-Za-z0-9])`, "gi"), target]);
  const shortRules = Object.entries(SHORT)
    .sort((a, b) => b[0].length - a[0].length)
    .map(([source, target]) => [new RegExp(`(?<![A-Za-z0-9])${escapeRegExp(source)}(?![A-Za-z0-9])`, "g"), target]);

  function localize(value) {
    let out = String(value || "");
    for (const [pattern, target] of phraseRules) out = out.replace(pattern, target);
    for (const [pattern, target] of shortRules) out = out.replace(pattern, target);
    return out;
  }

  function localizeTextNode(node) {
    if (!node || node.nodeType !== Node.TEXT_NODE || !node.parentElement) return;
    if (!node.nodeValue || !/[A-Za-z\u00C0-\u024F]/.test(node.nodeValue)) return;
    if (node.parentElement.closest(SKIP)) return;
    const next = localize(node.nodeValue);
    if (next !== node.nodeValue) node.nodeValue = next;
  }

  function scan(root = document) {
    const targets = [];
    if (root.nodeType === Node.TEXT_NODE) targets.push(root);
    if (root.nodeType === Node.ELEMENT_NODE && root.matches?.("main article")) {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) targets.push(walker.currentNode);
    } else {
      const scope = root.querySelectorAll ? root : document;
      scope.querySelectorAll?.("main article").forEach((article) => {
        const walker = document.createTreeWalker(article, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) targets.push(walker.currentNode);
      });
    }
    targets.forEach(localizeTextNode);
  }

  function boot() {
    scan(document);
    const main = document.querySelector("main") || document.body;
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type === "characterData") localizeTextNode(mutation.target);
        for (const node of mutation.addedNodes || []) {
          if (node.nodeType === Node.TEXT_NODE) localizeTextNode(node);
          else if (node.nodeType === Node.ELEMENT_NODE) scan(node);
        }
      }
    });
    observer.observe(main, { childList: true, subtree: true, characterData: true });
    window.HKTradDisplay = { localize, scan };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
