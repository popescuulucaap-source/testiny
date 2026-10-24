/* Gargand lion roar interaction. Site soundtrack controls live in the shared layout. */
document.addEventListener("DOMContentLoaded", () => {
  "use strict";

  let audioCtx = null;
  let master = null;

  const ensureAudio = () => {
    if (!audioCtx) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) return false;
      audioCtx = new AudioContextClass();
      master = audioCtx.createGain();
      master.gain.value = 0.16;
      master.connect(audioCtx.destination);
    }
    if (audioCtx.state === "suspended") audioCtx.resume().catch(() => {});
    return true;
  };

  const playRoar = () => {
    if (!ensureAudio()) return false;

    const now = audioCtx.currentTime;
    const duration = 1.35;
    const count = Math.ceil(audioCtx.sampleRate * duration);
    const buffer = audioCtx.createBuffer(1, count, audioCtx.sampleRate);
    const data = buffer.getChannelData(0);
    let smooth = 0;

    for (let i = 0; i < count; i++) {
      smooth = (smooth + (Math.random() * 2 - 1) * 0.11) / 1.11;
      data[i] = smooth * 8;
    }

    const source = audioCtx.createBufferSource();
    const band = audioCtx.createBiquadFilter();
    const shape = audioCtx.createWaveShaper();
    const noiseAmp = audioCtx.createGain();
    const curve = new Float32Array(1024);

    for (let i = 0; i < curve.length; i++) {
      const x = i * 2 / (curve.length - 1) - 1;
      curve[i] = Math.tanh(x * 3.2);
    }

    source.buffer = buffer;
    band.type = "bandpass";
    band.Q.value = 0.8;
    band.frequency.setValueAtTime(720, now);
    band.frequency.exponentialRampToValueAtTime(210, now + duration);
    shape.curve = curve;
    shape.oversample = "2x";
    noiseAmp.gain.setValueAtTime(0.0001, now);
    noiseAmp.gain.exponentialRampToValueAtTime(0.26, now + 0.12);
    noiseAmp.gain.setValueAtTime(0.20, now + 0.52);
    noiseAmp.gain.exponentialRampToValueAtTime(0.0001, now + duration);

    source.connect(band);
    band.connect(shape);
    shape.connect(noiseAmp);
    noiseAmp.connect(master);
    source.start(now);
    source.stop(now + duration + 0.03);

    const growl = audioCtx.createOscillator();
    const growlAmp = audioCtx.createGain();
    const growlFilter = audioCtx.createBiquadFilter();
    growl.type = "sawtooth";
    growl.frequency.setValueAtTime(78, now);
    growl.frequency.exponentialRampToValueAtTime(39, now + duration);
    growlFilter.type = "lowpass";
    growlFilter.frequency.value = 280;
    growlAmp.gain.setValueAtTime(0.0001, now);
    growlAmp.gain.exponentialRampToValueAtTime(0.10, now + 0.15);
    growlAmp.gain.exponentialRampToValueAtTime(0.0001, now + duration);
    growl.connect(growlFilter);
    growlFilter.connect(growlAmp);
    growlAmp.connect(master);
    growl.start(now);
    growl.stop(now + duration + 0.03);
    return true;
  };

  const roarButton = document.getElementById("ggLionRoar");
  const stage = document.querySelector(".gg-hero-art");
  const status = document.getElementById("ggLionRoarStatus");
  let lastRoarAt = 0;

  if (roarButton && stage) {
    roarButton.addEventListener("click", () => {
      if (performance.now() - lastRoarAt < 2200) return;
      lastRoarAt = performance.now();
      const played = playRoar();
      stage.classList.remove("roaring");
      void stage.offsetWidth;
      stage.classList.add("roaring");

      if (status) {
        status.textContent = played
          ? "The crowned guardian answers."
          : "Sound is unavailable in this browser.";
      }

      window.setTimeout(() => {
        stage.classList.remove("roaring");
        if (status) status.textContent = "Tap again when you want to hear it.";
      }, 1450);
    });
  }

  if (stage && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
    stage.addEventListener("pointermove", event => {
      const rect = stage.getBoundingClientRect();
      const x = (event.clientX - rect.left) / rect.width - 0.5;
      const y = (event.clientY - rect.top) / rect.height - 0.5;
      stage.style.setProperty("--lion-tilt-x", `${(-y * 5).toFixed(2)}deg`);
      stage.style.setProperty("--lion-tilt-y", `${(x * 6).toFixed(2)}deg`);
    }, { passive: true });

    stage.addEventListener("pointerleave", () => {
      stage.style.setProperty("--lion-tilt-x", "0deg");
      stage.style.setProperty("--lion-tilt-y", "0deg");
    }, { passive: true });
  }
});
