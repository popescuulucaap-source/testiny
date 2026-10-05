document.addEventListener('DOMContentLoaded',()=>{
  const loader=document.getElementById('nightfall-loader');
  if(loader){
    const key='nightfall-home-intro-seen-v2';
    if(sessionStorage.getItem(key)) loader.remove();
    else {
      sessionStorage.setItem(key,'1');
      const bar=loader.querySelector('.intro-progress-fill');
      const label=loader.querySelector('.intro-progress-label');
      const start=performance.now(),duration=4000;
      const step=now=>{
        const progress=Math.min(1,(now-start)/duration);
        if(bar)bar.style.transform=`scaleX(${progress})`;
        if(label)label.textContent=`${Math.round(progress*100)}%`;
        if(progress<1)requestAnimationFrame(step);
        else {loader.classList.add('hidden');setTimeout(()=>loader.remove(),650);}
      };
      requestAnimationFrame(step);
    }
  }

  document.querySelectorAll('.tab').forEach(button=>button.addEventListener('click',()=>{
    document.querySelectorAll('.tab').forEach(item=>item.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(panel=>panel.classList.remove('active'));
    button.classList.add('active');
    document.getElementById(button.dataset.tab)?.classList.add('active');
  }));

  document.querySelectorAll('.save-settings').forEach(button=>button.addEventListener('click',async()=>{
    const group=button.closest('.setting-group'),result=group.querySelector('.save-result'),payload={};
    try{
      group.querySelectorAll('[data-setting]').forEach(field=>{
        const key=field.dataset.setting;
        if(field.type==='checkbox')payload[key]=field.checked;
        else if(key==='ticket_options')payload[key]=field.value.split(',').map(x=>x.trim()).filter(Boolean);
        else if(key==='ticket_questions')payload[key]=JSON.parse(field.value||'{}');
        else payload[key]=field.value.trim();
      });
      result.textContent='Saving settings…';button.disabled=true;
      const response=await fetch(`/api/dashboard/${window.NIGHTFALL_GUILD_ID}/settings`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const data=await response.json();
      result.textContent=data.ok?'✓ Settings queued. Nightfall applies them on its next check-in.':`✕ ${data.error||'Could not save settings.'}`;
      result.classList.toggle('error',!data.ok);
    }catch(error){result.textContent=error instanceof SyntaxError?'✕ Ticket questions must be valid JSON.':'✕ Dashboard connection failed.';result.classList.add('error');}
    finally{button.disabled=false;}
  }));

  document.querySelectorAll('.bot-action').forEach(button=>button.addEventListener('click',async()=>{
    const result=document.getElementById('actionResult');button.disabled=true;result.textContent='Sending action to Nightfall…';
    try{
      const response=await fetch(`/api/dashboard/${window.NIGHTFALL_GUILD_ID}/action`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:button.dataset.action})});
      const data=await response.json();result.textContent=data.ok?'✓ Action queued. Nightfall will process it on its next check-in.':`✕ ${data.error||'Action failed.'}`;result.classList.toggle('error',!data.ok);
    }catch(error){result.textContent='✕ Dashboard connection failed.';result.classList.add('error');}
    finally{button.disabled=false;}
  }));

  const targets=document.querySelectorAll('.hero-copy,.hero-card,.section-heading,.card,.cta,.command-card,.server-card,.home-ribbon,.workflow-art,.workflow-copy,.command-stack');
  if(!('IntersectionObserver'in window)){targets.forEach(element=>element.classList.add('is-visible'));return;}
  targets.forEach(element=>element.classList.add('reveal'));
  const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){entry.target.classList.add('is-visible');observer.unobserve(entry.target);}}),{threshold:.12});
  targets.forEach(element=>observer.observe(element));

  const consoleCard=document.querySelector('.home-console');
  if(consoleCard&&!matchMedia('(prefers-reduced-motion: reduce)').matches){
    consoleCard.addEventListener('pointermove',event=>{
      const rect=consoleCard.getBoundingClientRect();
      consoleCard.style.setProperty('--px',`${event.clientX-rect.left}px`);
      consoleCard.style.setProperty('--py',`${event.clientY-rect.top}px`);
    },{passive:true});
  }

  // Nightfall audio: an original cinematic night-sky soundtrack + subtle UI tones.
  // Browsers require a user gesture before sound can begin.
  let audioCtx=null,master=null,ambientGain=null,ambientTimer=null,audioOn=localStorage.getItem('nightfall-audio')!=='off';
  const audioButton=document.createElement('button');
  audioButton.className='nightfall-audio-toggle';
  audioButton.type='button';
  audioButton.setAttribute('aria-label','Toggle Nightfall ambient audio');
  audioButton.innerHTML='<span>◉</span><b>Night Sky</b><small>ON</small>';
  document.body.appendChild(audioButton);

  const ensureAudio=()=>{
    if(!audioCtx){
      audioCtx=new (window.AudioContext||window.webkitAudioContext)();
      master=audioCtx.createGain();
      master.gain.value=.22;
      master.connect(audioCtx.destination);
    }
    if(audioCtx.state==='suspended')audioCtx.resume();
  };
  const note=(freq,dur,type='sine',gain=.035,when=0)=>{
    ensureAudio();
    const t=audioCtx.currentTime+when,o=audioCtx.createOscillator(),g=audioCtx.createGain(),f=audioCtx.createBiquadFilter();
    o.type=type;o.frequency.setValueAtTime(freq,t);
    f.type='lowpass';f.frequency.value=1800;
    g.gain.setValueAtTime(.0001,t);
    g.gain.exponentialRampToValueAtTime(gain,t+.08);
    g.gain.exponentialRampToValueAtTime(.0001,t+dur);
    o.connect(f);f.connect(g);g.connect(master);o.start(t);o.stop(t+dur+.05);
  };
  const startAmbient=()=>{
    ensureAudio();
    if(ambientTimer)return;
    if(!ambientGain){
      ambientGain=audioCtx.createGain();
      ambientGain.gain.value=.72;
      ambientGain.connect(master);
    }
    const play=()=>{
      if(!audioOn)return;
      const now=audioCtx.currentTime;
      const songs=[
        [110,164.81,220,329.63,493.88,659.25],
        [98,146.83,196,293.66,440,587.33],
        [123.47,164.81,246.94,369.99,493.88,739.99],
        [92.5,138.59,184.99,277.18,415.3,622.25]
      ];
      const scale=songs[Math.floor(Date.now()/12000)%songs.length];
      // Warm pad
      scale.slice(0,3).forEach((f,i)=>{
        const o=audioCtx.createOscillator(),g=audioCtx.createGain(),filter=audioCtx.createBiquadFilter();
        o.type=i===0?'triangle':'sine';o.frequency.value=f;
        filter.type='lowpass';filter.frequency.value=1200;
        g.gain.setValueAtTime(.0001,now);
        g.gain.exponentialRampToValueAtTime(.06,now+.9);
        g.gain.exponentialRampToValueAtTime(.0001,now+10.8);
        o.connect(filter);filter.connect(g);g.connect(ambientGain);o.start(now);o.stop(now+11.1);
      });
      // Slow arpeggio
      [scale[3],scale[4],scale[5],scale[4],scale[3],scale[5]].forEach((f,i)=>{
        const t=i*1.45;
        note(f,1.15,'sine',.024,t);
        note(f/2,1.5,'triangle',.012,t);
      });
      ambientTimer=setTimeout(()=>{ambientTimer=null;play();},9200);
    };
    play();
  };
  const stopAmbient=()=>{
    if(ambientTimer){clearTimeout(ambientTimer);ambientTimer=null;}
    if(ambientGain&&audioCtx){
      ambientGain.gain.cancelScheduledValues(audioCtx.currentTime);
      ambientGain.gain.setTargetAtTime(.0001,audioCtx.currentTime,.18);
    }
  };
  const setAudio=on=>{
    audioOn=on;localStorage.setItem('nightfall-audio',on?'on':'off');
    audioButton.classList.toggle('on',on);
    audioButton.querySelector('small').textContent=on?'ON':'OFF';
    if(on){
      if(ambientGain&&audioCtx)ambientGain.gain.setTargetAtTime(.72,audioCtx.currentTime,.25);
      startAmbient();
      note(659.25,.16,'sine',.045);note(783.99,.22,'sine',.032,.07);note(987.77,.28,'sine',.022,.14);
    }else stopAmbient();
  };
  audioButton.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();setAudio(!audioOn);});
  audioButton.classList.toggle('on',audioOn);
  document.addEventListener('pointerdown',event=>{
    if(event.target.closest('.nightfall-audio-toggle'))return;
    if(audioOn){ensureAudio();startAmbient();}
  },{capture:true,passive:true});
  document.querySelectorAll('a.btn,.nav-links a,button:not(.nightfall-audio-toggle)').forEach(el=>el.addEventListener('click',()=>{
    if(audioOn){ensureAudio();startAmbient();note(659.25,.08,'sine',.022);note(880,.12,'sine',.016,.045);}
  },{passive:true}));
  document.querySelectorAll('.home-feature-card,.command-line,.home-cta,.card').forEach(el=>el.addEventListener('mouseenter',()=>{
    if(audioOn)note(740,.05,'sine',.012);
  },{passive:true}));

  // ===== SINGLE HIDDEN SECRET =====
  // Only the marked secret star can unlock the mini-game. Ten clicks are required.
  const secretStar=document.querySelector('[data-secret-star]');
  const duckGame=document.getElementById('duckGame');
  const duckField=document.getElementById('duckField');
  const duckStart=document.getElementById('duckStart');
  const duckStartBtn=document.getElementById('duckStartBtn');
  const duckClose=document.getElementById('duckClose');
  const duckHitsEl=document.getElementById('duckHits');
  const duckTimeEl=document.getElementById('duckTime');
  const duckResult=document.getElementById('duckResult');
  let starClicks=0, starLast=0, duckTimer=null, duckTime=30, duckHits=0, duckRunning=false, duckDeadline=0;

  const closeDuckGame=()=>{
    if(duckTimer){clearInterval(duckTimer);duckTimer=null;}
    duckRunning=false;
    if(duckGame){duckGame.hidden=true;document.body.classList.remove('duck-game-open');}
  };
  const finishDuckGame=async(won)=>{
    if(duckTimer){clearInterval(duckTimer);duckTimer=null;}
    duckRunning=false;
    if(!won){
      stopCarnivalMusic(); playArcadeSound('lose'); duckResult.innerHTML='<strong>Challenge over.</strong><span>You did not finish in time. Your account can still try the challenge again, but it can only ever earn one arcade reward.</span>';
      return;
    }
    try{
      const response=await fetch('/api/arcade/finish',{method:'POST',headers:{'Content-Type':'application/json'}});
      const raw=await response.text();
      let data={};
      try{data=JSON.parse(raw);}catch(e){
        throw new Error(response.ok?'The reward system returned an invalid response.':'The reward server failed while creating your code. Please try again.');
      }
      if(!response.ok||!data.ok) throw new Error(data.error||'Could not create your code.');
      stopCarnivalMusic(); playArcadeSound('win'); duckResult.innerHTML='<strong>50% OFF CODE UNLOCKED.</strong><span>Your one-time code is:</span><code class="duck-reward-code">ducky-squad</code><span>Save it now. It is tied to this Discord account and can only be redeemed once.</span><a class="btn primary duck-redeem-link" href="/redeem">Redeem code</a>';
      localStorage.removeItem('nightfall-duck-discount');
    }catch(error){
      duckResult.innerHTML='<strong>Reward error.</strong><span>'+String(error.message||'Please try again.')+'</span>';
    }
  };
  const moveDuck=()=>{
    if(!duckField)return;
    const old=duckField.querySelector('.duck-target'); if(old)old.remove();
    const duck=document.createElement('button');
    duck.type='button';duck.className='duck-target';duck.setAttribute('aria-label','Duck target');
    duck.innerHTML='<span class="duck-body"></span><span class="duck-head"><i class="duck-eye"></i></span><span class="duck-wing"></span>';
    duck.style.left=(8+Math.random()*82)+'%';
    duck.style.top=(12+Math.random()*68)+'%';
    duck.addEventListener('click',async()=>{
      if(!duckRunning)return;
      duckRunning=false;
      try{
        const response=await fetch('/api/arcade/hit',{method:'POST',headers:{'Content-Type':'application/json'}});
        const data=await response.json();
        if(!response.ok||!data.ok) throw new Error(data.error||'Hit could not be recorded.');
        duckHits=data.hits; playArcadeSound('hit');
        duckHitsEl.textContent=duckHits;
        duck.classList.add('duck-hit');
        setTimeout(()=>duck.remove(),90);
        if(duckHits>=10){await finishDuckGame(true);return;}
        duckRunning=true;
        setTimeout(moveDuck,120);
      }catch(error){
        duckRunning=false;
        duckResult.innerHTML='<strong>Challenge stopped.</strong><span>'+String(error.message||'Could not record the hit.')+'</span>';
      }
    });
    duckField.appendChild(duck);
  };

  let carnivalAudio=null;
  const playArcadeSound=(type)=>{
    try{
      const ctx=new (window.AudioContext||window.webkitAudioContext)();
      const osc=ctx.createOscillator(), gain=ctx.createGain();
      osc.type=type==='hit'?'square':'triangle';
      osc.frequency.value=type==='hit'?520:260;
      gain.gain.setValueAtTime(.06,ctx.currentTime); gain.gain.exponentialRampToValueAtTime(.001,ctx.currentTime+.12);
      osc.connect(gain);gain.connect(ctx.destination);osc.start();osc.stop(ctx.currentTime+.12);
    }catch(e){}
  };
  // Secret-game music: one short loop, one AudioContext, and a hard stop.
  // This intentionally replaces the old layered carnival loop that could overlap.
  let carnivalAudio=null;
  const startCarnivalMusic=()=>{
    if(carnivalAudio || !audioCtx) return;
    try{
      ensureAudio();
      const ctx=audioCtx;
      const gain=ctx.createGain();
      gain.gain.value=.045;
      gain.connect(master);
      carnivalAudio={gain,timer:null,oscillators:[]};
      const notes=[261.63,329.63,392,523.25,392,329.63,293.66,349.23];
      let step=0;
      const play=()=>{
        if(!carnivalAudio)return;
        const now=ctx.currentTime;
        const o=ctx.createOscillator(),g=ctx.createGain();
        o.type='sine';o.frequency.value=notes[step%notes.length];
        g.gain.setValueAtTime(.0001,now);
        g.gain.exponentialRampToValueAtTime(.12,now+.02);
        g.gain.exponentialRampToValueAtTime(.0001,now+.22);
        o.connect(g);g.connect(gain);o.start(now);o.stop(now+.24);
        carnivalAudio.oscillators.push(o);
        step++;
        carnivalAudio.timer=setTimeout(play,260);
      };
      play();
    }catch(e){ carnivalAudio=null; }
  };
  const stopCarnivalMusic=()=>{
    const music=carnivalAudio;
    carnivalAudio=null;
    if(!music)return;
    if(music.timer)clearTimeout(music.timer);
    try{
      music.oscillators.forEach(o=>{try{o.stop();}catch(e){}});
      if(music.gain&&audioCtx){
        music.gain.gain.cancelScheduledValues(audioCtx.currentTime);
        music.gain.gain.setTargetAtTime(.0001,audioCtx.currentTime,.03);
      }
    }catch(e){}
  };
  const startDuckGame=async()=>{
    if(!duckGame)return;
    if(duckTimer){clearInterval(duckTimer);duckTimer=null;}
    try{
      const response=await fetch('/api/arcade/start',{method:'POST',headers:{'Content-Type':'application/json'}});
      const data=await response.json();
      if(!response.ok||!data.ok){duckResult.innerHTML='<strong>Already claimed.</strong><span>'+String(data.error||'You cannot earn another arcade code.')+'</span>';return;}
    }catch(error){duckResult.innerHTML='<strong>Challenge unavailable.</strong><span>Could not connect to the reward system.</span>';return;}
    duckRunning=true;duckHits=0;duckTime=30; startCarnivalMusic(); playArcadeSound('start');duckDeadline=Date.now()+30000;
    duckHitsEl.textContent='0';duckTimeEl.textContent='30';duckResult.textContent='';
    if(duckStart){duckStart.hidden=true;duckStart.style.display='none';}
    duckGame?.classList.add('is-running');
    moveDuck();
    duckTimer=setInterval(()=>{
      const remaining=Math.max(0,duckDeadline-Date.now());
      duckTime=Math.ceil(remaining/1000);
      duckTimeEl.textContent=duckTime;
      if(remaining<=0)finishDuckGame(false);
    },100);
  };
  const openDuckGame=()=>{
    if(!duckGame)return;
    duckGame.hidden=false; duckGame.classList.remove("is-running");document.body.classList.add('duck-game-open');
    location.hash='duck-hunt';
    duckResult.innerHTML='<strong>Secret unlocked.</strong><span>Complete the arcade challenge to unlock 50% off Premium.</span>';
    window.scrollTo({top:0,behavior:'smooth'});
  };
  if(secretStar){
    secretStar.addEventListener('click',event=>{
    event.preventDefault();event.stopPropagation();
    const now=Date.now();
    starClicks=now-starLast<5000?starClicks+1:1;
    starLast=now;
    secretStar.classList.add('secret-star-hit');
    setTimeout(()=>secretStar.classList.remove('secret-star-hit'),500);
    if(starClicks>=1){starClicks=0;openDuckGame();}
  });
  }
  duckStartBtn?.addEventListener('click',startDuckGame);
  duckClose?.addEventListener('click',closeDuckGame);
  duckGame?.addEventListener('click',event=>{if(event.target===duckGame)closeDuckGame();});
  // Rewards are now stored server-side and tied to the logged-in Discord account.

});