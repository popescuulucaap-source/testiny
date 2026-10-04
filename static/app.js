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

  // Nightfall easter eggs — all client-side and intentionally harmless.
  const egg=document.querySelector('.easter-egg-panel');
  const toast=document.createElement('div');
  toast.className='nightfall-secret-toast';
  toast.setAttribute('role','status');
  toast.setAttribute('aria-live','polite');
  document.body.appendChild(toast);
  let toastTimer=null;
  const showSecret=(title,message)=>{
    if(egg){egg.hidden=false;egg.scrollIntoView({behavior:'smooth',block:'center'});}
    toast.innerHTML='<b>✦ '+title+'</b><span>'+message+'</span>';
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer=setTimeout(()=>toast.classList.remove('show'),4200);
    if(audioOn){ensureAudio();note(493.88,.16,'sine',.03);note(659.25,.22,'sine',.024,.09);note(987.77,.3,'sine',.018,.18);}
  };
  let secret='';
  document.addEventListener('keydown',event=>{
    if(event.ctrlKey||event.altKey||event.metaKey)return;
    if(event.key.length===1){
      secret=(secret+event.key.toLowerCase()).slice(-8);
      if(secret==='nightfall'){secret='';showSecret('SECRET SIGNAL 01','You found the quiet side of Nightfall. ✦');}
    }
  });
  const secretLogo=document.querySelector('.home-mark');
  if(secretLogo){
    let clicks=0,last=0;
    secretLogo.addEventListener('click',()=>{
      const now=Date.now();
      clicks=now-last<1400?clicks+1:1;last=now;
      if(clicks>=5){clicks=0;showSecret('SECRET SIGNAL 02','The emblem noticed you. Keep looking around. ✦');}
    });
  }
  document.querySelectorAll('.visual-star').forEach(star=>star.addEventListener('click',event=>{
    event.preventDefault();
    showSecret('SECRET SIGNAL 03','A star has fallen into Nightfall. ✧');
    star.classList.add('secret-star-hit');
    setTimeout(()=>star.classList.remove('secret-star-hit'),900);
  }));

});
