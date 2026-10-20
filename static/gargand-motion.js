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
