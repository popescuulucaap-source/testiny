/* Scroll reveals are progressive enhancement: content stays visible if unsupported or motion is reduced. */
(()=>{
  const reduced=window.matchMedia&&window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if(reduced||!("IntersectionObserver" in window))return;
  const selectors=[
    "#main-content > section",
    "#main-content .page-head",
    "#main-content .gg-section-head",
    "#main-content .gg-feature",
    "#main-content .gg-command-preview",
    "#main-content .command-grid",
    "#main-content .update-center",
    "#main-content .support-choice-grid",
    "#main-content .support-panel",
    "#main-content .dashboard-metrics",
    "#main-content .dashboard-grid",
    "#main-content .server-grid",
    "#main-content .gg-info-strip",
    ".gg-footer-top",
    ".gg-developers",
    ".gg-owner-card",
    ".gg-footer-bottom"
  ];
  const elements=new Set();
  selectors.forEach(selector=>document.querySelectorAll(selector).forEach(element=>elements.add(element)));
  if(!elements.size)return;
  document.documentElement.classList.add("gg-motion-ready");
  const observer=new IntersectionObserver(entries=>{
    entries.forEach(entry=>{
      if(!entry.isIntersecting)return;
      entry.target.classList.add("is-visible");
      observer.unobserve(entry.target);
    });
  },{threshold:.12,rootMargin:"0px 0px -36px 0px"});
  let index=0;
  elements.forEach(element=>{
    element.classList.add("gg-reveal");
    element.style.setProperty("--gg-reveal-delay",Math.min(index++%5,4)*55+"ms");
    observer.observe(element);
  });
})();

/* Hidden crown: the classic Konami sequence reveals a lightweight lion toast. */
(()=>{
  const code=["ArrowUp","ArrowUp","ArrowDown","ArrowDown","ArrowLeft","ArrowRight","ArrowLeft","ArrowRight","b","a"];
  let position=0;
  const editable=el=>el&&(/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)||el.isContentEditable);
  function reveal(){
    if(document.querySelector(".gg-crown-secret"))return;
    const veil=document.createElement("div");veil.className="gg-crown-secret";veil.setAttribute("role","dialog");veil.setAttribute("aria-modal","true");veil.setAttribute("aria-label","Gargand's hidden crown");
    const card=document.createElement("div");card.className="gg-crown-secret-card";
    const close=document.createElement("button");close.type="button";close.className="gg-crown-secret-close";close.setAttribute("aria-label","Close");close.textContent="×";
    const crown=document.createElement("span");crown.className="gg-crown-secret-icon";crown.setAttribute("aria-hidden","true");crown.textContent="♛";
    const title=document.createElement("strong");title.textContent="THE CROWN REMEMBERS";
    const message=document.createElement("p");message.textContent="You found Gargand's hidden crest. The pride welcomes you.";
    const mark=document.createElement("small");mark.textContent="✦ GARGAND • COMMUNITY SYSTEMS ✦";
    card.append(close,crown,title,message,mark);veil.append(card);document.body.append(veil);
    const dismiss=()=>{veil.remove();document.removeEventListener("keydown",onEscape);};
    const onEscape=e=>{if(e.key==="Escape")dismiss();};
    close.addEventListener("click",dismiss);veil.addEventListener("click",e=>{if(e.target===veil)dismiss();});card.addEventListener("click",e=>e.stopPropagation());document.addEventListener("keydown",onEscape);close.focus();window.setTimeout(dismiss,6500);
  }
  window.addEventListener("keydown",event=>{
    if(editable(event.target)||event.ctrlKey||event.metaKey||event.altKey)return;
    const key=event.key.length===1?event.key.toLowerCase():event.key;
    if(key===code[position]){position++;if(position===code.length){position=0;reveal();}}
    else position=key===code[0]?1:0;
  });
})();