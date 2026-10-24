/* Immersive Gargand product scene: loops in-page, stays muted until requested, and falls back to a native web animation. */
(() => {
  "use strict";
  const film=document.getElementById("ggCinematicFilm");
  if(!film)return;
  const video=film.querySelector("#ggFilmVideo");
  const scenes=Array.from(film.querySelectorAll("[data-film-scene-panel]"));
  const chapters=Array.from(film.querySelectorAll("[data-film-chapter]"));
  const segments=Array.from(film.querySelectorAll("[data-film-segment]"));
  const playButton=film.querySelector("[data-film-play]");
  const pauseButton=film.querySelector("[data-film-pause]");
  const previousButton=film.querySelector("[data-film-previous]");
  const nextButton=film.querySelector("[data-film-next]");
  const position=film.querySelector("[data-film-position]");
  const status=film.querySelector("[data-film-status]");
  const soundButton=film.querySelector("[data-film-sound]");
  if(!scenes.length||!playButton)return;
  const sceneDuration=5700;
  const titles=["A new guardian rises","Security, layer by layer","Moderation with clarity","Community stays connected","Your control room","Command the chaos"];
  const reducedMotion=window.matchMedia&&window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let current=0,timer=0,playing=false,videoReady=false,manualPaused=false,inView=false,suspended=false;
  const clearTimer=()=>{if(timer)window.clearTimeout(timer);timer=0;};
  const clampIndex=value=>Math.max(0,Math.min(scenes.length-1,value));
  function paint(){
    film.dataset.filmState=playing?"playing":(current===scenes.length-1&&film.dataset.finished==="1"?"complete":"paused");
    film.dataset.filmScene=String(current);
    scenes.forEach((scene,index)=>{const active=index===current;scene.classList.toggle("is-active",active);scene.setAttribute("aria-hidden",active?"false":"true");});
    chapters.forEach((button,index)=>{const active=index===current;button.classList.toggle("is-active",active);if(active)button.setAttribute("aria-current","step");else button.removeAttribute("aria-current");});
    const complete=film.dataset.filmState==="complete";
    const sceneSeconds=videoReady&&video.duration?video.duration/scenes.length:sceneDuration/1000;
    const withinScene=videoReady&&video.duration?(video.currentTime%sceneSeconds)/sceneSeconds:(playing?0.52:0);
    segments.forEach((button,index)=>{button.classList.toggle("is-past",index<current||complete);button.classList.toggle("is-current",index===current&&!complete);const fill=button.querySelector("span");if(fill)fill.style.width=index<current||complete?"100%":(index===current?String(Math.max(0,Math.min(100,withinScene*100)))+"%":"0%");});
    if(position)position.textContent="CHAPTER "+String(current+1).padStart(2,"0")+" / "+String(scenes.length).padStart(2,"0");
    if(status)status.textContent=playing?"IMMERSIVE MODE · "+titles[current].toUpperCase():(complete?"SHOWCASE COMPLETE":(reducedMotion?"MOTION REDUCED · "+titles[current].toUpperCase():(manualPaused?"PAUSED · "+titles[current].toUpperCase():"READY TO EXPLORE")));
    playButton.innerHTML='<span class="gg-film-play-symbol" aria-hidden="true">'+(playing?"Ⅱ":"▶")+'</span>'+(manualPaused?"RESUME SHOWCASE":"PLAY THE SHOWCASE");
    if(pauseButton){pauseButton.textContent=playing?"Pause motion":"Play motion";pauseButton.setAttribute("aria-label",playing?"Pause cinematic motion":"Play cinematic motion");}
    if(previousButton)previousButton.disabled=current===0;
    if(nextButton)nextButton.disabled=current===scenes.length-1;
    if(soundButton){const on=!!(video&&!video.muted);soundButton.textContent=on?"♫ SOUND ON":"♫ SOUND OFF";soundButton.setAttribute("aria-pressed",on?"true":"false");soundButton.setAttribute("aria-label",on?"Mute cinematic soundtrack":"Enable cinematic soundtrack");soundButton.classList.toggle("is-on",on);}
  }
  function finishFallback(){
    clearTimer();
    if(!playing||videoReady)return;
    current=(current+1)%scenes.length;
    paint();
    scheduleFallback();
  }
  function scheduleFallback(){
    clearTimer();
    if(!playing||videoReady||suspended)return;
    timer=window.setTimeout(finishFallback,sceneDuration);
  }
  function start(userRequested=false){
    if(userRequested)manualPaused=false;
    if(manualPaused||suspended||(!inView&&!userRequested))return;
    film.dataset.finished="0";
    playing=true;
    paint();
    if(videoReady&&video){
      if(video.ended)video.currentTime=0;
      const attempt=video.play();
      if(attempt&&typeof attempt.catch==="function")attempt.catch(()=>{videoReady=false;film.classList.remove("has-video");scheduleFallback();});
    }else{
      if(video&&video.networkState===HTMLMediaElement.NETWORK_EMPTY)video.load();
      scheduleFallback();
    }
  }
  function pause(userRequested=true){
    clearTimer();
    if(userRequested)manualPaused=true;
    playing=false;
    if(videoReady&&video&&!video.paused)video.pause();
    paint();
  }
  function goTo(index){
    current=clampIndex(index);
    film.dataset.finished="0";
    if(videoReady&&video&&video.duration)video.currentTime=Math.min(video.duration-.05,current*(video.duration/scenes.length));
    paint();
    if(playing&&!videoReady)scheduleFallback();
  }
  playButton.addEventListener("click",()=>playing?pause(true):start(true));
  if(pauseButton)pauseButton.addEventListener("click",()=>playing?pause(true):start(true));
  if(previousButton)previousButton.addEventListener("click",()=>goTo(current-1));
  if(nextButton)nextButton.addEventListener("click",()=>goTo(current+1));
  chapters.forEach(button=>button.addEventListener("click",()=>goTo(Number(button.dataset.filmChapter))));
  segments.forEach(button=>button.addEventListener("click",()=>goTo(Number(button.dataset.filmSegment))));
  if(soundButton)soundButton.addEventListener("click",()=>{
    if(!video)return;
    video.muted=!video.muted;
    video.volume=.72;
    if(video.muted===false&&!playing)start(true);
    paint();
  });
  film.addEventListener("keydown",event=>{
    if(event.altKey||event.ctrlKey||event.metaKey||/^(INPUT|TEXTAREA|SELECT|BUTTON)$/.test(event.target.tagName))return;
    if(event.key==="ArrowRight"){event.preventDefault();goTo(current+1);}
    if(event.key==="ArrowLeft"){event.preventDefault();goTo(current-1);}
    if(event.key==="Escape"&&playing)pause(true);
  });
  if(video){
    video.muted=true;video.loop=true;video.playsInline=true;
    video.addEventListener("loadedmetadata",()=>{
      if(!Number.isFinite(video.duration)||video.duration<=0)return;
      videoReady=true;film.classList.add("has-video");
      current=clampIndex(Math.floor(video.currentTime/(video.duration/scenes.length)));
      paint();
      if(playing&&!suspended&&!manualPaused){
        const attempt=video.play();
        if(attempt&&typeof attempt.catch==="function")attempt.catch(()=>{videoReady=false;film.classList.remove("has-video");scheduleFallback();});
      }
    });
    video.addEventListener("play",()=>{
      if(!videoReady)return;
      clearTimer();playing=true;film.dataset.finished="0";film.classList.add("has-video");paint();
    });
    video.addEventListener("pause",()=>{
      if(!videoReady||video.ended||suspended)return;
      if(manualPaused){playing=false;clearTimer();paint();}
    });
    video.addEventListener("timeupdate",()=>{
      if(!videoReady||!video.duration)return;
      current=clampIndex(Math.floor(video.currentTime/(video.duration/scenes.length)));
      paint();
    });
    video.addEventListener("error",()=>{
      videoReady=false;film.classList.remove("has-video");
      if(!manualPaused&&inView){playing=true;scheduleFallback();}
      paint();
    });
  }
  const visibilityObserver="IntersectionObserver"in window?new IntersectionObserver(entries=>{
    entries.forEach(entry=>{
      if(entry.target!==film)return;
      inView=entry.isIntersecting&&entry.intersectionRatio>=.08;
      if(!inView){
        suspended=true;clearTimer();
        if(videoReady&&video&&!video.paused)video.pause();
        playing=false;paint();
      }else{
        suspended=false;
        if(!manualPaused&&!reducedMotion)start(false);
      }
    });
  },{threshold:[0,.08,.2],rootMargin:"80px 0px 80px 0px"}):null;
  if(visibilityObserver)visibilityObserver.observe(film);
  else{inView=true;if(!reducedMotion)start(false);}
  document.addEventListener("visibilitychange",()=>{
    if(document.hidden){
      suspended=true;clearTimer();if(videoReady&&video&&!video.paused)video.pause();playing=false;paint();
    }else{
      suspended=false;
      if(inView&&!manualPaused&&!reducedMotion)start(false);
    }
  });
  film.dataset.finished="0";
  paint();
})();
