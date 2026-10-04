document.addEventListener('DOMContentLoaded',()=>{
  // Account progression: meaningful sections award a small, server-side XP bonus once per hour.
  const xpActions={"/":"profile","/community":"community","/suggestions":"suggestion","/secrets":"secrets"};
  const xpAction=xpActions[location.pathname];
  if(xpAction) fetch('/api/xp/award',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:xpAction})}).catch(()=>{});

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

  // ===== NIGHTFALL 100-SECRET CODE HUNT =====
  // Discovery/redeem UI only. Actual Premium activation will be added later.
  const secretCodes=[{"code":"STARR10","reward":"10% off Premium","type":"discount","value":10},{"code":"NF002UME7YRJ","reward":"10% off Premium","type":"discount","value":10},{"code":"NF00392TLD6X","reward":"15% off Premium","type":"discount","value":15},{"code":"NF004NF8ZSKC","reward":"5% off Premium","type":"discount","value":5},{"code":"NF0053UME7YR","reward":"10% off Premium","type":"discount","value":10},{"code":"NF006G92TLD6","reward":"15% off Premium","type":"discount","value":15},{"code":"NF007VNF8ZSK","reward":"5% off Premium","type":"discount","value":5},{"code":"NF008A3UME7Y","reward":"10% off Premium","type":"discount","value":10},{"code":"NF009PG92TLD","reward":"15% off Premium","type":"discount","value":15},{"code":"NF0104VNF8ZS","reward":"1 day of Premium","type":"free","value":1},{"code":"NF011HA3UME7","reward":"10% off Premium","type":"discount","value":10},{"code":"NF012WPG92TL","reward":"15% off Premium","type":"discount","value":15},{"code":"NF013B4VNF8Z","reward":"5% off Premium","type":"discount","value":5},{"code":"NF014QHA3UME","reward":"10% off Premium","type":"discount","value":10},{"code":"NF0155WPG92T","reward":"15% off Premium","type":"discount","value":15},{"code":"NF016JB4VNF8","reward":"5% off Premium","type":"discount","value":5},{"code":"NF017XQHA3UM","reward":"10% off Premium","type":"discount","value":10},{"code":"NF018C5WPG92","reward":"15% off Premium","type":"discount","value":15},{"code":"NF019RJB4VNF","reward":"5% off Premium","type":"discount","value":5},{"code":"NF0206XQHA3U","reward":"2 days of Premium","type":"free","value":2},{"code":"NF021KC5WPG9","reward":"15% off Premium","type":"discount","value":15},{"code":"NF022YRJB4VN","reward":"5% off Premium","type":"discount","value":5},{"code":"NF023D6XQHA3","reward":"10% off Premium","type":"discount","value":10},{"code":"NF024SKC5WPG","reward":"15% off Premium","type":"discount","value":15},{"code":"NF0257YRJB4V","reward":"5% off Premium","type":"discount","value":5},{"code":"NF026LD6XQHA","reward":"10% off Premium","type":"discount","value":10},{"code":"NF027ZSKC5WP","reward":"15% off Premium","type":"discount","value":15},{"code":"NF028E7YRJB4","reward":"5% off Premium","type":"discount","value":5},{"code":"NF029TLD6XQH","reward":"10% off Premium","type":"discount","value":10},{"code":"NF0308ZSKC5W","reward":"3 days of Premium","type":"free","value":3},{"code":"NF031ME7YRJB","reward":"5% off Premium","type":"discount","value":5},{"code":"NF0322TLD6XQ","reward":"10% off Premium","type":"discount","value":10},{"code":"NF033F8ZSKC5","reward":"15% off Premium","type":"discount","value":15},{"code":"NF034UME7YRJ","reward":"5% off Premium","type":"discount","value":5},{"code":"NF03592TLD6X","reward":"10% off Premium","type":"discount","value":10},{"code":"NF036NF8ZSKC","reward":"15% off Premium","type":"discount","value":15},{"code":"NF0373UME7YR","reward":"5% off Premium","type":"discount","value":5},{"code":"NF038G92TLD6","reward":"10% off Premium","type":"discount","value":10},{"code":"NF039VNF8ZSK","reward":"15% off Premium","type":"discount","value":15},{"code":"NF040A3UME7Y","reward":"1 day of Premium","type":"free","value":1},{"code":"NF041PG92TLD","reward":"10% off Premium","type":"discount","value":10},{"code":"NF0424VNF8ZS","reward":"15% off Premium","type":"discount","value":15},{"code":"NF043HA3UME7","reward":"5% off Premium","type":"discount","value":5},{"code":"NF044WPG92TL","reward":"10% off Premium","type":"discount","value":10},{"code":"NF045B4VNF8Z","reward":"15% off Premium","type":"discount","value":15},{"code":"NF046QHA3UME","reward":"5% off Premium","type":"discount","value":5},{"code":"NF0475WPG92T","reward":"10% off Premium","type":"discount","value":10},{"code":"NF048JB4VNF8","reward":"15% off Premium","type":"discount","value":15},{"code":"NF049XQHA3UM","reward":"5% off Premium","type":"discount","value":5},{"code":"NF050C5WPG92","reward":"2 days of Premium","type":"free","value":2},{"code":"NF051RJB4VNF","reward":"15% off Premium","type":"discount","value":15},{"code":"NF0526XQHA3U","reward":"5% off Premium","type":"discount","value":5},{"code":"NF053KC5WPG9","reward":"10% off Premium","type":"discount","value":10},{"code":"NF054YRJB4VN","reward":"15% off Premium","type":"discount","value":15},{"code":"NF055D6XQHA3","reward":"5% off Premium","type":"discount","value":5},{"code":"NF056SKC5WPG","reward":"10% off Premium","type":"discount","value":10},{"code":"NF0577YRJB4V","reward":"15% off Premium","type":"discount","value":15},{"code":"NF058LD6XQHA","reward":"5% off Premium","type":"discount","value":5},{"code":"NF059ZSKC5WP","reward":"10% off Premium","type":"discount","value":10},{"code":"NF060E7YRJB4","reward":"3 days of Premium","type":"free","value":3},{"code":"NF061TLD6XQH","reward":"5% off Premium","type":"discount","value":5},{"code":"NF0628ZSKC5W","reward":"10% off Premium","type":"discount","value":10},{"code":"NF063ME7YRJB","reward":"15% off Premium","type":"discount","value":15},{"code":"NF0642TLD6XQ","reward":"5% off Premium","type":"discount","value":5},{"code":"NF065F8ZSKC5","reward":"10% off Premium","type":"discount","value":10},{"code":"NF066UME7YRJ","reward":"15% off Premium","type":"discount","value":15},{"code":"NF06792TLD6X","reward":"5% off Premium","type":"discount","value":5},{"code":"NF068NF8ZSKC","reward":"10% off Premium","type":"discount","value":10},{"code":"NF0693UME7YR","reward":"15% off Premium","type":"discount","value":15},{"code":"NF070G92TLD6","reward":"1 day of Premium","type":"free","value":1},{"code":"NF071VNF8ZSK","reward":"10% off Premium","type":"discount","value":10},{"code":"NF072A3UME7Y","reward":"15% off Premium","type":"discount","value":15},{"code":"NF073PG92TLD","reward":"5% off Premium","type":"discount","value":5},{"code":"NF0744VNF8ZS","reward":"10% off Premium","type":"discount","value":10},{"code":"NF075HA3UME7","reward":"15% off Premium","type":"discount","value":15},{"code":"NF076WPG92TL","reward":"5% off Premium","type":"discount","value":5},{"code":"NF077B4VNF8Z","reward":"10% off Premium","type":"discount","value":10},{"code":"NF078QHA3UME","reward":"15% off Premium","type":"discount","value":15},{"code":"NF0795WPG92T","reward":"5% off Premium","type":"discount","value":5},{"code":"NF080JB4VNF8","reward":"2 days of Premium","type":"free","value":2},{"code":"NF081XQHA3UM","reward":"15% off Premium","type":"discount","value":15},{"code":"NF082C5WPG92","reward":"5% off Premium","type":"discount","value":5},{"code":"NF083RJB4VNF","reward":"10% off Premium","type":"discount","value":10},{"code":"NF0846XQHA3U","reward":"15% off Premium","type":"discount","value":15},{"code":"NF085KC5WPG9","reward":"5% off Premium","type":"discount","value":5},{"code":"NF086YRJB4VN","reward":"10% off Premium","type":"discount","value":10},{"code":"NF087D6XQHA3","reward":"15% off Premium","type":"discount","value":15},{"code":"NF088SKC5WPG","reward":"5% off Premium","type":"discount","value":5},{"code":"NF0897YRJB4V","reward":"10% off Premium","type":"discount","value":10},{"code":"NF090LD6XQHA","reward":"3 days of Premium","type":"free","value":3},{"code":"NF091ZSKC5WP","reward":"5% off Premium","type":"discount","value":5},{"code":"NF092E7YRJB4","reward":"10% off Premium","type":"discount","value":10},{"code":"NF093TLD6XQH","reward":"15% off Premium","type":"discount","value":15},{"code":"NF0948ZSKC5W","reward":"5% off Premium","type":"discount","value":5},{"code":"NF095ME7YRJB","reward":"10% off Premium","type":"discount","value":10},{"code":"NF0962TLD6XQ","reward":"15% off Premium","type":"discount","value":15},{"code":"NF097F8ZSKC5","reward":"5% off Premium","type":"discount","value":5},{"code":"NF098UME7YRJ","reward":"10% off Premium","type":"discount","value":10},{"code":"NF09992TLD6X","reward":"15% off Premium","type":"discount","value":15},{"code":"NF100NF8ZSKC","reward":"1 day of Premium","type":"free","value":1}];
  const foundKey='nightfall-found-secrets-v1';
  let foundSecrets=[];try{foundSecrets=JSON.parse(localStorage.getItem(foundKey)||'[]').filter(n=>Number.isInteger(n)&&n>=0&&n<100);}catch(_){}
  const foundSet=new Set(foundSecrets);
  const countEl=document.getElementById('secretCount'),codeForm=document.getElementById('nightfallCodeForm'),codeInput=document.getElementById('nightfallCodeInput'),codeResult=document.getElementById('nightfallCodeResult');
  const updateFoundCount=()=>{if(countEl)countEl.textContent=`${foundSet.size} / 100 FOUND`};const saveFound=()=>localStorage.setItem(foundKey,JSON.stringify([...foundSet]));updateFoundCount();
  const revealSecret=(index,title='SECRET SIGNAL')=>{if(index<0||index>=100||foundSet.has(index))return;foundSet.add(index);saveFound();updateFoundCount();showSecret(`${title} ${String(index+1).padStart(2,'0')}`,`You found a hidden code: ${secretCodes[index].code}. ✦`)};
  const discoverNext=()=>{for(let i=0;i<100;i++)if(!foundSet.has(i)){revealSecret(i);return true}return false};
  if(codeForm)codeForm.addEventListener('submit',event=>{event.preventDefault();const entered=(codeInput?.value||'').trim().toUpperCase(),index=secretCodes.findIndex(item=>item.code===entered);if(index<0){codeResult.textContent='✕ That code does not exist.';return}if(!foundSet.has(index)){codeResult.textContent='✕ You have not found this secret yet. Keep hunting.';return}codeResult.textContent=`✓ ${secretCodes[index].code}: ${secretCodes[index].reward}. Premium rewards are coming soon.`;codeInput.value='';if(audioOn){ensureAudio();note(659.25,.13,'sine',.028);note(880,.18,'sine',.022,.08)}});
  // Starr is intentionally hidden: the visible SECRET button is gone. Find it by clicking the logo 7 times.
  const secretLogo=document.querySelector('.home-mark');if(secretLogo){let clicks=0,last=0;secretLogo.addEventListener('click',()=>{const now=Date.now();clicks=now-last<1500?clicks+1:1;last=now;if(clicks>=7){clicks=0;revealSecret(0,'STARR EASTER EGG')}})}
  document.querySelectorAll('.visual-star').forEach((star,i)=>star.addEventListener('click',event=>{event.preventDefault();revealSecret([1,2,3][i],'STAR SIGNAL');star.classList.add('secret-star-hit');setTimeout(()=>star.classList.remove('secret-star-hit'),900)}));
  document.querySelectorAll('.home-feature-card').forEach((card,i)=>card.addEventListener('dblclick',()=>revealSecret(4+i,'HIDDEN FEATURE')));
  document.querySelectorAll('.command-line').forEach((line,i)=>line.addEventListener('dblclick',()=>revealSecret(10+i,'COMMAND SIGNAL')));
  let huntClicks=0,huntTimer=null;document.addEventListener('click',event=>{if(event.target.closest('a,button,input,textarea,select,.home-mark,.visual-star,.nightfall-audio-toggle'))return;huntClicks++;clearTimeout(huntTimer);huntTimer=setTimeout(()=>huntClicks=0,2600);if(huntClicks>=9){huntClicks=0;discoverNext()}},{passive:true});

});
