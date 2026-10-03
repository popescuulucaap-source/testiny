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
});
