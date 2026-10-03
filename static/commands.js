document.addEventListener('DOMContentLoaded',()=>{
  const cards=[...document.querySelectorAll('.command-card')];
  const search=document.getElementById('commandSearch');
  const count=document.getElementById('commandCount');
  const empty=document.getElementById('noCommands');
  let category='all';
  const update=()=>{
    const query=(search?.value||'').trim().toLowerCase();let visible=0;
    cards.forEach(card=>{const matches=(category==='all'||card.dataset.category===category)&&card.dataset.search.includes(query);card.hidden=!matches;if(matches)visible++;});
    if(count)count.textContent=`${visible} command${visible===1?'':'s'}`;
    if(empty)empty.hidden=visible!==0;
  };
  search?.addEventListener('input',update);
  document.querySelectorAll('.command-filter').forEach(button=>button.addEventListener('click',()=>{
    category=button.dataset.category.toLowerCase();
    document.querySelectorAll('.command-filter').forEach(item=>item.classList.toggle('active',item===button));update();
  }));
  document.querySelectorAll('.copy-command').forEach(button=>button.addEventListener('click',async()=>{
    try{await navigator.clipboard.writeText(button.dataset.copy);button.textContent='Copied';}
    catch{button.textContent='Select command';}
    setTimeout(()=>button.textContent='Copy',1300);
  }));
  update();
});

