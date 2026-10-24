/* Unique silent cinematic backplates on each Gargand tab, built from the same gold/space visual world. */
(() => {
  "use strict";
  const reduced=window.matchMedia&&window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const saveData=!!(navigator.connection&&navigator.connection.saveData);
  const path=window.location.pathname.replace(/\/+$/,"")||"/";
  const scenes={
    "/":"home","/commands":"commands","/security":"security","/verification":"verification",
    "/support":"support","/announcements":"announcements","/servers":"dashboard","/dashboard":"dashboard",
    "/admin":"dashboard","/admin/audit":"dashboard","/admin/community":"community","/admin/support":"support",
    "/guild/analytics":"dashboard","/guild/moderation":"security","/socials":"community","/profile":"community",
    "/passport":"community","/achievements":"community","/leaderboards":"community","/daily":"community",
    "/notifications":"announcements","/suggestions":"community","/suggestions/list":"community",
    "/guidelines":"security","/terms":"verification","/login":"home"
  };
  let kind=scenes[path];
  if(!kind&&/^\/dashboard\/\d+(?:\/|$)/.test(path)){
    kind=/analytics/.test(path)?"dashboard":(/moderation/.test(path)?"security":"dashboard");
  }
  if(!kind||reduced||saveData)return;
  const targets=path==="/"
    ? [document.querySelector(".gg-hero")]
    : [document.querySelector("#main-content > .page-head"),document.querySelector("#main-content > .dashboard-header"),document.querySelector("#main-content > .server-header"),document.querySelector("#main-content > .dashboard-head")].filter(Boolean);
  targets.filter(Boolean).forEach((target,slot)=>{
    if(target.querySelector(":scope > .gg-page-scene"))return;
    target.classList.add("gg-has-page-scene");
    const wrapper=document.createElement("div");
    wrapper.className="gg-page-scene";wrapper.setAttribute("aria-hidden","true");wrapper.dataset.sceneKind=kind;
    const video=document.createElement("video");
    video.className="gg-page-scene-video";video.muted=true;video.defaultMuted=true;video.autoplay=true;video.loop=true;video.playsInline=true;
    video.preload=slot===0?"metadata":"none";video.setAttribute("muted","");video.setAttribute("playsinline","");video.setAttribute("aria-hidden","true");
    video.disablePictureInPicture=true;video.src="/static/gargand-scenes/"+kind+".mp4?v=20261024-worldtabs2";
    const grain=document.createElement("span");grain.className="gg-page-scene-grain";
    wrapper.append(video,grain);target.prepend(wrapper);
    const play=video.play();if(play&&typeof play.catch==="function")play.catch(()=>{wrapper.classList.add("is-static");});
    const visibility="IntersectionObserver"in window?new IntersectionObserver(entries=>{
      entries.forEach(entry=>{if(entry.isIntersecting){if(video.paused)video.play().catch(()=>{});}else if(!video.paused)video.pause();});
    },{threshold:.01,rootMargin:"100px 0px"}):null;
    if(visibility)visibility.observe(target);
    document.addEventListener("visibilitychange",()=>{
      if(document.hidden){if(!video.paused)video.pause();}
      else if(!reduced&&!saveData&&target.getBoundingClientRect().bottom>0&&target.getBoundingClientRect().top<window.innerHeight)video.play().catch(()=>{});
    });
  });
  // Internal dashboard tabs swap their own moving backplate to match the selected tool.
  const dashboardScene=document.querySelector("#main-content .gg-page-scene");
  if(dashboardScene){
    const video=dashboardScene.querySelector("video");
    const sceneForLabel=label=>{
      const value=(label||"").toLowerCase();
      if(/security|moderat|audit|incident/.test(value))return "security";
      if(/command|bot|setup|music/.test(value))return "commands";
      if(/support|ticket|community|member|social|profile/.test(value))return "community";
      if(/notification|announcement|release|activity/.test(value))return "announcements";
      return "dashboard";
    };
    document.querySelectorAll('[role="tab"],[data-tab],.dashboard-tab,.tab-button').forEach(button=>{
      button.addEventListener("click",()=>{
        const next=sceneForLabel(button.textContent||button.getAttribute("aria-label"));
        const source="/static/gargand-scenes/"+next+".mp4?v=20261024-worldtabs2";
        if(video&&video.getAttribute("src")!==source){video.src=source;video.load();video.play().catch(()=>{});}
        dashboardScene.dataset.sceneKind=next;
      });
    });
  }
})();
