(function(){
  var search = document.getElementById('commandSearch');
  var grid = document.getElementById('commandGrid');
  if (!grid) return;
  var cards = Array.prototype.slice.call(grid.querySelectorAll('.command-card'));
  var filters = Array.prototype.slice.call(document.querySelectorAll('.command-filter'));
  var count = document.getElementById('commandCount');
  var empty = document.getElementById('noCommands');
  var activeCategory = 'all';
  function update(){
    var query = search ? search.value.trim().toLowerCase() : '';
    var shown = 0;
    cards.forEach(function(card){
      var category = (card.getAttribute('data-category') || '').toLowerCase();
      var haystack = (card.getAttribute('data-search') || card.textContent || '').toLowerCase();
      var matches = (activeCategory === 'all' || category === activeCategory.toLowerCase()) && (!query || haystack.indexOf(query) !== -1);
      card.hidden = !matches;
      if (matches) shown++;
    });
    if (count) count.textContent = shown + ' command' + (shown === 1 ? '' : 's') + ' shown';
    if (empty) empty.hidden = shown !== 0;
  }
  if (search) search.addEventListener('input', update);
  filters.forEach(function(button){
    button.addEventListener('click', function(){
      activeCategory = button.getAttribute('data-category') || 'all';
      filters.forEach(function(other){other.classList.toggle('active', other === button);});
      update();
    });
  });
  grid.addEventListener('click', function(event){
    var button = event.target.closest('[data-copy]');
    if (!button) return;
    var value = button.getAttribute('data-copy') || '';
    function success(){button.textContent='Copied ✓';window.setTimeout(function(){button.textContent='Copy';},1400);}
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(value).then(success).catch(function(){fallback();});
    } else fallback();
    function fallback(){
      var field=document.createElement('textarea');field.value=value;field.setAttribute('readonly','');field.style.position='fixed';field.style.opacity='0';document.body.appendChild(field);field.select();
      try{document.execCommand('copy');success();}catch(e){button.textContent='Select command';}
      field.remove();
    }
  });
  update();
})();