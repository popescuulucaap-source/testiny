document.addEventListener('DOMContentLoaded',()=>{
  // The score and lion effect are generated locally. Nothing plays until a visitor
  // presses a sound control, so the page remains quiet and needs no external media.
  let audioCtx=null,master=null,ambientGain=null,ambientTimer=null,noiseNode=null,musicOn=false;
  const soundButton=document.createElement('button');
  soundButton.className='nightfall-audio-toggle gargand-audio-toggle';
  soundButton.type='button';
  soundButton.setAttribute('aria-label','Play or pause the Gargand soundtrack');
  soundButton.innerHTML='<span>♫</span><b>Gargand score</b><small>OFF</small>';
  document.body.appendChild(soundButton);

  const ensureAudio=()=>{
    if(!audioCtx){
      const AudioContextClass=window.AudioContext||window.webkitAudioContext;
      if(!AudioContextClass)return false;
      audioCtx=new AudioContextClass();
      master=audioCtx.createGain();master.gain.value=.16;master.connect(audioCtx.destination);
    }
    if(audioCtx.state==='suspended')audioCtx.resume().catch(()=>{});
    return true;
  };
  const note=(freq,duration,gain,delay=0)=>{
    const start=audioCtx.currentTime+delay,osc=audioCtx.createOscillator(),amp=audioCtx.createGain(),filter=audioCtx.createBiquadFilter();
    osc.type='sine';osc.frequency.value=freq;filter.type='lowpass';filter.frequency.value=900;
    amp.gain.setValueAtTime(.0001,start);amp.gain.exponentialRampToValueAtTime(gain,start+.16);amp.gain.exponentialRampToValueAtTime(.0001,start+duration);
    osc.connect(filter);filter.connect(amp);amp.connect(ambientGain);osc.start(start);osc.stop(start+duration+.04);
  };
  const startMusic=()=>{
    if(!ensureAudio()||ambientTimer)return;
    if(!ambientGain){ambientGain=audioCtx.createGain();ambientGain.gain.value=.0001;ambientGain.connect(master);}
    ambientGain.gain.setTargetAtTime(.55,audioCtx.currentTime,.35);
    if(!noiseNode){
      const buffer=audioCtx.createBuffer(1,audioCtx.sampleRate*2,audioCtx.sampleRate),samples=buffer.getChannelData(0);
      let smooth=0;for(let i=0;i<samples.length;i++){smooth=(smooth+(Math.random()*2-1)*.05)/1.05;samples[i]=smooth*5;}
      noiseNode=audioCtx.createBufferSource();const filter=audioCtx.createBiquadFilter(),amp=audioCtx.createGain();
      noiseNode.buffer=buffer;noiseNode.loop=true;filter.type='lowpass';filter.frequency.value=260;amp.gain.value=.004;
      noiseNode.connect(filter);filter.connect(amp);amp.connect(ambientGain);noiseNode.start();
    }
    const playPhrase=()=>{
      if(!musicOn)return;
      const now=audioCtx.currentTime;
      const chords=[[55,82.41,110,164.81],[49,73.42,98,146.83],[61.74,92.5,123.47,185]];
      const chord=chords[Math.floor(Date.now()/18000)%chords.length];
      chord.slice(0,3).forEach((frequency,index)=>{
        const osc=audioCtx.createOscillator(),amp=audioCtx.createGain(),filter=audioCtx.createBiquadFilter();
        osc.type=index?'sine':'triangle';osc.frequency.value=frequency;filter.type='lowpass';filter.frequency.value=650+index*160;
        amp.gain.setValueAtTime(.0001,now);amp.gain.exponentialRampToValueAtTime(.032/(index+1),now+1.4);amp.gain.exponentialRampToValueAtTime(.0001,now+16);
        osc.connect(filter);filter.connect(amp);amp.connect(ambientGain);osc.start(now);osc.stop(now+16.1);
      });
      note(chord[3],2,.009,2.4);note(chord[3]*1.5,2.4,.007,6.8);note(chord[3]*2,2.6,.006,11.5);
      ambientTimer=window.setTimeout(()=>{ambientTimer=null;playPhrase();},15000);
    };
    playPhrase();
  };
  const stopMusic=()=>{
    if(ambientTimer){clearTimeout(ambientTimer);ambientTimer=null;}
    if(ambientGain&&audioCtx)ambientGain.gain.setTargetAtTime(.0001,audioCtx.currentTime,.22);
    if(noiseNode){try{noiseNode.stop();}catch(error){}noiseNode=null;}
  };
  soundButton.addEventListener('click',()=>{
    musicOn=!musicOn;soundButton.classList.toggle('on',musicOn);soundButton.querySelector('small').textContent=musicOn?'ON':'OFF';
    if(musicOn){if(ensureAudio())startMusic();else{musicOn=false;soundButton.classList.remove('on');soundButton.querySelector('small').textContent='N/A';}}
    else stopMusic();
  });

  const playRoar=()=>{
    if(!ensureAudio())return false;
    const now=audioCtx.currentTime,duration=1.35,count=Math.ceil(audioCtx.sampleRate*duration),buffer=audioCtx.createBuffer(1,count,audioCtx.sampleRate),data=buffer.getChannelData(0);
    let smooth=0;for(let i=0;i<count;i++){smooth=(smooth+(Math.random()*2-1)*.11)/1.11;data[i]=smooth*8;}
    const source=audioCtx.createBufferSource(),band=audioCtx.createBiquadFilter(),shape=audioCtx.createWaveShaper(),noiseAmp=audioCtx.createGain(),curve=new Float32Array(1024);
    for(let i=0;i<curve.length;i++){const x=i*2/(curve.length-1)-1;curve[i]=Math.tanh(x*3.2);}
    source.buffer=buffer;band.type='bandpass';band.Q.value=.8;band.frequency.setValueAtTime(720,now);band.frequency.exponentialRampToValueAtTime(210,now+duration);
    shape.curve=curve;shape.oversample='2x';noiseAmp.gain.setValueAtTime(.0001,now);noiseAmp.gain.exponentialRampToValueAtTime(.26,now+.12);noiseAmp.gain.setValueAtTime(.20,now+.52);noiseAmp.gain.exponentialRampToValueAtTime(.0001,now+duration);
    source.connect(band);band.connect(shape);shape.connect(noiseAmp);noiseAmp.connect(master);source.start(now);source.stop(now+duration+.03);
    const growl=audioCtx.createOscillator(),growlAmp=audioCtx.createGain(),growlFilter=audioCtx.createBiquadFilter();
    growl.type='sawtooth';growl.frequency.setValueAtTime(78,now);growl.frequency.exponentialRampToValueAtTime(39,now+duration);growlFilter.type='lowpass';growlFilter.frequency.value=280;
    growlAmp.gain.setValueAtTime(.0001,now);growlAmp.gain.exponentialRampToValueAtTime(.10,now+.15);growlAmp.gain.exponentialRampToValueAtTime(.0001,now+duration);
    growl.connect(growlFilter);growlFilter.connect(growlAmp);growlAmp.connect(master);growl.start(now);growl.stop(now+duration+.03);
    return true;
  };
  const roarButton=document.getElementById('ggLionRoar'),stage=document.querySelector('.gg-hero-art'),status=document.getElementById('ggLionRoarStatus');
  let lastRoarAt=0;
  if(roarButton&&stage){
    roarButton.addEventListener('click',()=>{
      if(performance.now()-lastRoarAt<2200)return;
      lastRoarAt=performance.now();const played=playRoar();
      stage.classList.remove('roaring');void stage.offsetWidth;stage.classList.add('roaring');
      if(status)status.textContent=played?'The crowned guardian answers.':'Sound is unavailable in this browser.';
      window.setTimeout(()=>{stage.classList.remove('roaring');if(status)status.textContent='Tap again when you want to hear it.';},1450);
    });
  }
  if(stage&&!matchMedia('(prefers-reduced-motion: reduce)').matches){
    stage.addEventListener('pointermove',event=>{
      const rect=stage.getBoundingClientRect(),x=(event.clientX-rect.left)/rect.width-.5,y=(event.clientY-rect.top)/rect.height-.5;
      stage.style.setProperty('--lion-tilt-x',`${(-y*5).toFixed(2)}deg`);stage.style.setProperty('--lion-tilt-y',`${(x*6).toFixed(2)}deg`);
    },{passive:true});
    stage.addEventListener('pointerleave',()=>{stage.style.setProperty('--lion-tilt-x','0deg');stage.style.setProperty('--lion-tilt-y','0deg');},{passive:true});
  }
});
