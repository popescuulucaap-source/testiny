document.addEventListener("DOMContentLoaded", () => {
  const page = document.querySelector(".home-page");
  if (!page) return;

  const toast = document.createElement("div");
  toast.className = "nf-egg-toast";
  document.body.appendChild(toast);
  let toastTimer;

  const say = (title, text) => {
    toast.innerHTML = "<b>✦ " + title + "</b><span>" + text + "</span>";
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 3600);
  };

  const codes = [
    "STARR10","NF002UME7YRJ","NF00392TLD6X","NF004NF8ZSKC","NF0053UME7YR","NF006G92TLD6",
    "NF007VNF8ZSK","NF008A3UME7Y","NF009PG92TLD","NF0104VNF8ZS","NF011HA3UME7","NF012WPG92TL",
    "NF013B4VNF8Z","NF014QHA3UME","NF0155WPG92T","NF016JB4VNF8","NF017XQHA3UM","NF018C5WPG92",
    "NF019RJB4VNF","NF0206XQHA3U","NF021KC5WPG9","NF022YRJB4VN","NF023D6XQHA3","NF024SKC5WPG",
    "NF0257YRJB4V","NF026LD6XQHA","NF027ZSKC5WP","NF028E7YRJB4","NF029TLD6XQH","NF0308ZSKC5W",
    "NF031ME7YRJB","NF0322TLD6XQ","NF033F8ZSKC5","NF034UME7YRJ","NF03592TLD6X","NF036NF8ZSKC",
    "NF0373UME7YR","NF038G92TLD6","NF039VNF8ZSK","NF040A3UME7Y","NF041PG92TLD","NF0424VNF8ZS",
    "NF043HA3UME7","NF044WPG92TL","NF045B4VNF8Z","NF046QHA3UME","NF0475WPG92T","NF048JB4VNF8",
    "NF049XQHA3UM","NF050C5WPG92","NF051RJB4VNF","NF0526XQHA3U","NF053KC5WPG9","NF054YRJB4VN",
    "NF055D6XQHA3","NF056SKC5WPG","NF0577YRJB4V","NF058LD6XQHA","NF059ZSKC5WP","NF060E7YRJB4",
    "NF061TLD6XQH","NF0628ZSKC5W","NF063ME7YRJB","NF0642TLD6XQ","NF065F8ZSKC5","NF066UME7YRJ",
    "NF06792TLD6X","NF068NF8ZSKC","NF0693UME7YR","NF070G92TLD6","NF071VNF8ZSK","NF072A3UME7Y",
    "NF073PG92TLD","NF0744VNF8ZS","NF075HA3UME7","NF076WPG92TL","NF077B4VNF8Z","NF078QHA3UME",
    "NF0795WPG92T","NF080JB4VNF8","NF081XQHA3UM","NF082C5WPG92","NF083RJB4VNF","NF0846XQHA3U",
    "NF085KC5WPG9","NF086YRJB4VN","NF087D6XQHA3","NF088SKC5WPG","NF0897YRJB4V","NF090LD6XQHA",
    "NF091ZSKC5WP","NF092E7YRJB4","NF093TLD6XQH","NF0948ZSKC5W","NF095ME7YRJB","NF0962TLD6XQ",
    "NF097F8ZSKC5","NF098UME7YRJ","NF09992TLD6X","NF100NF8ZSKC"
  ];
  const rewards = codes.map((_, i) => i === 0 ? "10% off Premium" : (i % 10 === 9 ? ((i % 3) + 1) + " day(s) of Premium" : ((i % 3) + 1) * 5 + "% off Premium"));
  const foundKey = "nightfall-found-secrets-v2";
  let found = new Set();
  try { found = new Set(JSON.parse(localStorage.getItem(foundKey) || "[]").filter(n => Number.isInteger(n) && n >= 0 && n < 100)); } catch (_) {}
  const save = () => localStorage.setItem(foundKey, JSON.stringify([...found]));
  const count = document.getElementById("secretCount");
  const update = () => { if (count) count.textContent = found.size + " / 100 FOUND"; };
  update();

  const reveal = (n, title = "SECRET EGG") => {
    if (n < 0 || n >= 100 || found.has(n)) return;
    found.add(n); save(); update();
    say(title + " " + String(n + 1).padStart(2, "0"), "Code: " + codes[n] + " • Reward: " + rewards[n]);
    const panel = document.querySelector(".easter-egg-panel");
    if (panel) {
      panel.hidden = false;
      panel.innerHTML = '<span class="eyebrow">SECRET SIGNAL • ' + String(n + 1).padStart(2, "0") + '</span><h2>You found a Nightfall secret.</h2><p>Code <code>' + codes[n] + '</code> • ' + rewards[n] + '</p>';
    }
  };
  const next = (title) => { for (let i = 0; i < 100; i++) if (!found.has(i)) { reveal(i, title); return; } };

  // 01–10: classic signals
  const logo = document.querySelector(".home-mark");
  if (logo) {
    let c = 0, last = 0;
    logo.addEventListener("click", () => {
      const now = Date.now(); c = now - last < 1500 ? c + 1 : 1; last = now;
      if (c >= 7) { c = 0; reveal(0, "STARR EASTER EGG"); }
    });
  }
  document.querySelectorAll(".visual-star").forEach((el, i) => el.addEventListener("click", e => { e.preventDefault(); reveal(i + 1, "STAR SIGNAL"); }));
  document.querySelectorAll(".home-feature-card").forEach((el, i) => el.addEventListener("dblclick", () => reveal(4 + i, "FEATURE SECRET")));
  document.querySelectorAll(".command-line").forEach((el, i) => el.addEventListener("dblclick", () => reveal(11 + i, "COMMAND SECRET")));

  // 16–30: interaction eggs
  const interactions = [
    ["nav", () => document.querySelectorAll(".nav-links a")[0]],
    ["about", () => document.querySelector(".home-about")],
    ["workflow", () => document.querySelector(".home-workflow")],
    ["ribbon", () => document.querySelector(".home-ribbon")],
    ["suggestions", () => document.querySelector(".suggestion-hero")],
    ["premium", () => document.querySelector(".nightfall-premium-coming")],
    ["codes", () => document.querySelector(".nightfall-code-vault")],
    ["reviews", () => document.querySelector(".nightfall-reviews")],
    ["cta", () => document.querySelector(".home-cta")],
    ["status", () => document.querySelector(".nightfall-status-card")],
    ["eyebrow", () => document.querySelector(".home-eyebrow")],
    ["hero", () => document.querySelector(".hero-copy h1")],
    ["lead", () => document.querySelector(".lead")],
    ["trust", () => document.querySelector(".trust-row")],
    ["wordmark", () => document.querySelector(".about-wordmark-wrap")],
  ];
  interactions.forEach(([name, getter], i) => {
    const el = getter();
    if (!el) return;
    let armed = false;
    el.addEventListener("mouseenter", () => { if (!armed) { armed = true; setTimeout(() => armed = false, 1200); }});
    el.addEventListener("mouseleave", () => { if (armed) { reveal(16 + i, "HIDDEN " + name.toUpperCase()); armed = false; }});
  });

  // 31–45: keyboard signals. Harmless, no global shortcuts.
  const sequences = ["nf","moon","night","fall","star","orbit","guardian","afterdark","midnight","shadow","owl","luna","echo","void","dusk"];
  let typed = "";
  document.addEventListener("keydown", e => {
    if (e.ctrlKey || e.altKey || e.metaKey || e.key.length !== 1) return;
    typed = (typed + e.key.toLowerCase()).slice(-12);
    sequences.forEach((s, i) => { if (typed.endsWith(s)) reveal(31 + i, "KEYWORD SIGNAL"); });
  });

  // 46–60: scrolling / timing / cursor movement.
  let maxScroll = 0, moved = 0, lastMove = 0;
  window.addEventListener("scroll", () => {
    const pct = Math.round((scrollY / Math.max(1, document.documentElement.scrollHeight - innerHeight)) * 100);
    maxScroll = Math.max(maxScroll, pct);
    if (pct >= 10) reveal(46, "SCROLL SIGNAL");
    if (pct >= 25) reveal(47, "QUARTER MOON");
    if (pct >= 50) reveal(48, "HALF MOON");
    if (pct >= 75) reveal(49, "THREE QUARTERS");
    if (pct >= 99) reveal(50, "DEEP NIGHT");
  }, { passive: true });
  document.addEventListener("mousemove", e => {
    const now = Date.now();
    if (now - lastMove > 180) { moved++; lastMove = now; }
    if (moved >= 20) reveal(51, "TRAVELING STAR");
    if (e.clientX < 30) reveal(52, "LEFT EDGE");
    if (e.clientX > innerWidth - 30) reveal(53, "RIGHT EDGE");
    if (e.clientY < 30) reveal(54, "TOP EDGE");
    if (e.clientY > innerHeight - 30) reveal(55, "BOTTOM EDGE");
  }, { passive: true });
  setTimeout(() => reveal(56, "WAITING NIGHT"), 15000);
  setTimeout(() => reveal(57, "PATIENT NIGHT"), 30000);
  document.addEventListener("visibilitychange", () => { if (document.hidden) reveal(58, "THE NIGHT WATCHES"); });
  window.addEventListener("resize", () => reveal(59, "WINDOW SIGNAL"));
  window.addEventListener("online", () => reveal(60, "NETWORK SIGNAL"));

  // 61–75: tiny UI challenges
  const challenges = [
    ["CLICKER", () => { let n=0; return () => { if (++n >= 5) reveal(61, "FIVE FINGERS"); }; }],
    ["RHYTHM", () => { let last=0,n=0; return () => { const t=Date.now(); if(t-last>250&&t-last<900)n++; else n=1; last=t; if(n>=6) reveal(62,"RHYTHM SIGNAL"); }; }],
    ["DOUBLE", () => { let n=0; return () => { if(++n>=2) reveal(63,"DOUBLE TAP"); }; }],
    ["HOVER", () => { let n=0; return () => { if(++n>=4) reveal(64,"HOVER HUNT"); }; }],
    ["FOCUS", () => { let n=0; return () => { if(++n>=3) reveal(65,"FOCUS SIGNAL"); }; }]
  ];
  const challengeButtons = document.querySelectorAll("a.btn, .nav-links a, button");
  challenges.forEach(([_, make], i) => {
    const fn = make();
    challengeButtons.forEach(b => b.addEventListener(i === 0 ? "click" : i === 1 ? "click" : i === 2 ? "dblclick" : i === 3 ? "mouseenter" : "focus", fn));
  });
  document.querySelectorAll("input,textarea,select").forEach(el => {
    el.addEventListener("focus", () => reveal(66, "INPUT SIGNAL"));
    el.addEventListener("change", () => reveal(67, "CHANGE SIGNAL"));
  });
  document.querySelectorAll("form").forEach(form => form.addEventListener("reset", () => reveal(68, "RESET SIGNAL")));
  document.addEventListener("copy", () => reveal(69, "COPY SIGNAL"));
  document.addEventListener("cut", () => reveal(70, "CUT SIGNAL"));
  document.addEventListener("paste", () => reveal(71, "PASTE SIGNAL"));
  document.addEventListener("contextmenu", () => reveal(72, "RIGHT CLICK SIGNAL"));
  document.addEventListener("dblclick", () => reveal(73, "DOUBLE NIGHT"));
  document.addEventListener("pointerdown", () => reveal(74, "FIRST TOUCH"), { once: true });
  document.addEventListener("pointerup", () => reveal(75, "RELEASE SIGNAL"), { once: true });

  // 76–90: playable games and achievements.
  const gameBox = document.getElementById("nightfall-games");
  const result = document.getElementById("gameResult");
  const gameButtons = document.querySelectorAll("[data-game]");
  const setGame = name => {
    if (!result) return;
    const render = {
      coin: '<button class="game-action" id="coinBtn">FLIP COIN</button><p id="coinOut">Pick heads or tails.</p>',
      guess: '<input id="guessInput" type="number" min="1" max="20" placeholder="1–20"><button class="game-action" id="guessBtn">GUESS</button><p id="guessOut"></p>',
      reaction: '<button class="game-action" id="reactBtn">WAIT FOR GO…</button><p id="reactOut"></p>',
      memory: '<div class="memory-grid" id="memoryGrid"></div><p id="memoryOut"></p>',
      tap: '<button class="game-action" id="tapBtn">TAP ME 20 TIMES</button><p id="tapOut">0 / 20</p>'
    };
    result.innerHTML = render[name] || "";
    if (name === "coin") {
      let n=0; document.getElementById("coinBtn").onclick=()=>{ const v=Math.random()<.5?"HEADS":"TAILS"; document.getElementById("coinOut").textContent=v+" — nice flip."; if(++n>=3) reveal(76,"COINMASTER"); };
    }
    if (name === "guess") {
      const secret=Math.floor(Math.random()*20)+1; let tries=0;
      document.getElementById("guessBtn").onclick=()=>{ const g=Number(document.getElementById("guessInput").value); if(!g)return; tries++; const out=document.getElementById("guessOut"); if(g===secret){out.textContent="Correct!"; reveal(77,"GUESSER");} else out.textContent=g<secret?"Higher…":"Lower…"; if(tries>=8) reveal(78,"STUBBORN GUESSER"); };
    }
    if (name === "reaction") {
      const b=document.getElementById("reactBtn"), out=document.getElementById("reactOut"); let start=0, timer=setTimeout(()=>{b.textContent="GO! CLICK!";start=performance.now();},1500+Math.random()*2500);
      b.onclick=()=>{ if(!start){clearTimeout(timer);out.textContent="Too early!"; reveal(79,"FALSE START"); return;} out.textContent=Math.round(performance.now()-start)+" ms"; reveal(80,"REACTION NIGHT"); };
    }
    if (name === "tap") {
      let n=0; document.getElementById("tapBtn").onclick=()=>{n++;document.getElementById("tapOut").textContent=n+" / 20";if(n>=20)reveal(81,"TAP CHAMPION");};
    }
    if (name === "memory") {
      const vals=["✦","☾","✧","★","✦","☾","✧","★"].sort(()=>Math.random()-.5), grid=document.getElementById("memoryGrid"); let open=[],matched=0;
      vals.forEach((v,i)=>{const b=document.createElement("button");b.className="memory-card";b.textContent="?";b.dataset.v=v;b.onclick=()=>{if(open.includes(b)||b.disabled)return;b.textContent=v;open.push(b);if(open.length===2){if(open[0].dataset.v===open[1].dataset.v){open.forEach(x=>x.disabled=true);matched++;open=[];if(matched===4)reveal(82,"MEMORY KEEPER");}else{const pair=[...open];open=[];setTimeout(()=>pair.forEach(x=>x.textContent="?"),450);}}};grid.appendChild(b);});
    }
  };
  gameButtons.forEach(b => b.addEventListener("click", () => { setGame(b.dataset.game); reveal(83 + [...gameButtons].indexOf(b), "GAME DISCOVERY"); }));
  if (gameBox) gameBox.addEventListener("mouseenter", () => reveal(88, "ARCADE SHADOW"));
  document.addEventListener("keydown", e => { if(e.key==="ArrowUp") reveal(89,"UP ARROW"); if(e.key==="Escape") reveal(90,"ESCAPE SIGNAL"); });

  // 91–100: social / final secrets.
  const social = document.getElementById("nightfall-secret-social");
  if (social) {
    const openSocial = () => { social.hidden=false; social.scrollIntoView({behavior:"smooth",block:"center"}); reveal(91,"SECRET SOCIAL"); };
    const codeWord = ["s","o","c","i","a","l"];
    let typedSocial="";
    document.addEventListener("keydown", e => { if(e.key.length===1){typedSocial=(typedSocial+e.key.toLowerCase()).slice(-6);if(typedSocial===codeWord.join("")){typedSocial="";openSocial();}}});
    document.querySelector(".brand")?.addEventListener("contextmenu", e => { e.preventDefault(); openSocial(); });
    let footerClicks=0; document.querySelector("footer")?.addEventListener("click",()=>{if(++footerClicks>=5){footerClicks=0;openSocial();}});
    document.querySelector(".visual-caption")?.addEventListener("dblclick",openSocial);
  }
  document.querySelectorAll(".secret-social-link").forEach((el,i)=>el.addEventListener("click",()=>reveal(92+i,"SOCIAL SIGNAL")));

  // 100th egg: discover all others.
  const completion = () => { if(found.size >= 99) reveal(99,"THE FINAL NIGHT"); };
  setInterval(completion, 1200);

  // Safety net: if an old script already populated the counter, sync our set.
  const old = (() => { try { return JSON.parse(localStorage.getItem("nightfall-found-secrets-v1") || "[]"); } catch (_) { return []; }})();
  old.forEach(n => { if(Number.isInteger(n) && n >= 0 && n < 100) found.add(n); });
  save(); update();
});
