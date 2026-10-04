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

  // Nightfall audio: original ambient soundtrack + UI sounds.
  // Browsers require a user gesture, so the first click/tap can start it automatically.
  let audioCtx=null,master=null,ambientGain=null,ambientTimer=null,audioOn=localStorage.getItem('nightfall-audio')==='on';
  const audioButton=document.createElement('button');
  audioButton.className='nightfall-audio-toggle';
  audioButton.type='button';
  audioButton.setAttribute('aria-label','Toggle Nightfall ambient audio');
  audioButton.innerHTML='<span>◉</span><b>Ambient</b><small>OFF</small>';
  document.body.appendChild(audioButton);

  const ensureAudio=()=>{
    if(audioCtx)return;
    audioCtx=new (window.AudioContext||window.webkitAudioContext)();
    master=audioCtx.createGain();
    master.gain.value=.28;
    master.connect(audioCtx.destination);
  };
  const tone=(freq,dur,type='sine',gain=.06,delay=0)=>{
    ensureAudio();
    if(audioCtx.state==='suspended')audioCtx.resume();
    const t=audioCtx.currentTime+delay,o=audioCtx.createOscillator(),g=audioCtx.createGain();
    o.type=type;o.frequency.setValueAtTime(freq,t);
    g.gain.setValueAtTime(.0001,t);
    g.gain.exponentialRampToValueAtTime(gain,t+.025);
    g.gain.exponentialRampToValueAtTime(.0001,t+dur);
    o.connect(g);g.connect(master);o.start(t);o.stop(t+dur+.04);
  };
  const startAmbient=()=>{
    ensureAudio();
    if(audioCtx.state==='suspended')audioCtx.resume();
    if(ambientTimer)return;
    if(!ambientGain){ambientGain=audioCtx.createGain();ambientGain.gain.value=.7;ambientGain.connect(master);}
    const play=()=>{
      if(!audioCtx||!audioOn)return;
      const now=audioCtx.currentTime;
      // Original dreamy chord progression; not a recording of any commercial song.
      const chords=[[130.81,164.81,196,246.94],[146.83,174.61,220,293.66],[123.47,155.56,196,246.94],[138.59,174.61,207.65,277.18]];
      const chord=chords[Math.floor(Date.now()/7600)%chords.length];
      chord.forEach((f,i)=>{
        const o=audioCtx.createOscillator(),g=audioCtx.createGain(),filter=audioCtx.createBiquadFilter();
        o.type=i%2?'sine':'triangle';o.frequency.value=f;filter.type='lowpass';filter.frequency.value=1100;
        g.gain.setValueAtTime(.0001,now);g.gain.exponentialRampToValueAtTime(.055,now+.9);g.gain.exponentialRampToValueAtTime(.0001,now+7.2);
        o.connect(filter);filter.connect(g);g.connect(ambientGain);o.start(now);o.stop(now+7.4);
      });
      // Soft high notes for a more audible, colorful atmosphere.
      [392,493.88,587.33].forEach((f,i)=>tone(f,2.7,'sine',.018,i*1.9));
      ambientTimer=setTimeout(()=>{ambientTimer=null;play();},6800);
    };
    play();
  };
  const stopAmbient=()=>{
    if(ambientTimer){clearTimeout(ambientTimer);ambientTimer=null;}
    if(ambientGain){ambientGain.gain.cancelScheduledValues(audioCtx.currentTime);ambientGain.gain.setTargetAtTime(.0001,audioCtx.currentTime,.18);}
  };
  const setAudio=on=>{
    audioOn=on;localStorage.setItem('nightfall-audio',on?'on':'off');
    audioButton.classList.toggle('on',on);
    audioButton.querySelector('small').textContent=on?'ON':'OFF';
    if(on){startAmbient();tone(523.25,.18,'sine',.06);tone(783.99,.22,'sine',.045,.08);}
    else stopAmbient();
  };
  audioButton.addEventListener('click',event=>{event.stopPropagation();setAudio(!audioOn);});
  if(audioOn){audioButton.classList.add('on');audioButton.querySelector('small').textContent='ON';}
  // Any normal button/link click starts the saved ambient mode instead of accidentally turning it off.
  document.addEventListener('click',event=>{
    if(event.target.closest('.nightfall-audio-toggle'))return;
    if(audioOn){ensureAudio();startAmbient();tone(660,.07,'sine',.025);}
  },{capture:true});
  document.querySelectorAll('a.btn,.nav-links a').forEach(el=>el.addEventListener('click',()=>{
    if(matchMedia('(prefers-reduced-motion: reduce)').matches)return;
    if(audioOn){tone(520,.1,'sine',.035);tone(740,.13,'sine',.025,.05);}
  }));
  document.querySelectorAll('.home-feature-card,.command-line,.home-cta').forEach(el=>el.addEventListener('mouseenter',()=>{
    if(audioOn)tone(680,.06,'sine',.018);
  }));

});
