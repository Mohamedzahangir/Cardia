// =========================================================================
// CARDIA CLINICAL COCKPIT - REAL-TIME BACKEND INTEGRATION SCRIPT
// Connects UI to Live WebSocket Simulation, ML Predictor, and RAG Copilot
// =========================================================================

window.CARDIA_BACKEND = (function() {
  var h = window.location.hostname;
  if (h === 'localhost' || h === '127.0.0.1') return '';
  return 'https://cardia-0e68.onrender.com';
})();

(function() {
  window.__CARDIA_STATE = {
    // Patient Profile
    patient: {
      sex: "MALE",
      age: 48,
      weight: 74,
      height: 178,
      bsa: 1.91,
      state: "Euvolemic"
    },
    // Hemodynamics
    hr: 74,
    bloodVolume: 5.0,
    contractility: 1.0,
    svr: 1120,
    targetSbp: 118,
    targetDbp: 78,
    running: true,
    speed: 1.0,
    isOffline: false,
    aiOffline: false,
    cyclePhase: 0,
    lastFrameTime: performance.now(),
    // 3D Cardiac view controls
    viewRotX: 0.2,
    viewRotY: -0.4,
    viewZoom: 1.0,
    // Live metrics received from SimulationService
    live: {
      time_s: 0,
      map: 93,
      sbp: 118,
      dbp: 78,
      co: 5.4,
      sv: 73,
      edv: 128,
      esv: 44,
      ef: 65.6,
      cpp: 68,
      mvo2: 4.1,
      valves: {
        mitral: { is_open: true },
        aortic: { is_open: false },
        tricuspid: { is_open: true },
        pulmonic: { is_open: false }
      },
      chambers: {}
    }
  };

  const state = window.__CARDIA_STATE;

  // DOM Handles - Tabs
  const tabBtnPatient = document.getElementById('tab-btn-patient');
  const tabBtnKnobs = document.getElementById('tab-btn-knobs');
  const viewPatientProfile = document.getElementById('view-patient-profile');
  const viewPerturbations = document.getElementById('view-perturbations');

  if (tabBtnPatient && tabBtnKnobs) {
    tabBtnPatient.addEventListener('click', () => {
      tabBtnPatient.className = "px-2 py-0.5 rounded font-bold transition-all bg-white text-clinical-cyan shadow-xs";
      tabBtnKnobs.className = "px-2 py-0.5 rounded text-text-dim hover:text-text-primary transition-all";
      if (viewPatientProfile) viewPatientProfile.classList.remove('hidden');
      if (viewPerturbations) viewPerturbations.classList.add('hidden');
    });
    tabBtnKnobs.addEventListener('click', () => {
      tabBtnKnobs.className = "px-2 py-0.5 rounded font-bold transition-all bg-white text-clinical-cyan shadow-xs";
      tabBtnPatient.className = "px-2 py-0.5 rounded text-text-dim hover:text-text-primary transition-all";
      if (viewPerturbations) viewPerturbations.classList.remove('hidden');
      if (viewPatientProfile) viewPatientProfile.classList.add('hidden');
    });
  }

  // Patient Profile interactive fields
  const sexBtns = document.querySelectorAll('.sex-btn');
  sexBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      sexBtns.forEach(b => {
        b.className = "px-2 py-0.5 rounded text-text-dim hover:text-text-primary transition-all sex-btn";
      });
      btn.className = "px-2 py-0.5 rounded bg-clinical-cyan text-white font-bold transition-all sex-btn";
      state.patient.sex = btn.getAttribute('data-sex');
      flashSync();
    });
  });

  const inAge = document.getElementById('input-patient-age');
  const inWeight = document.getElementById('input-patient-weight');
  const inHeight = document.getElementById('input-patient-height');
  const dispBsa = document.getElementById('disp-patient-bsa');
  const selectState = document.getElementById('select-patient-state');
  const syncIndicator = document.getElementById('sync-indicator');

  function flashSync() {
    if (syncIndicator) {
      syncIndicator.textContent = "SAVED";
      syncIndicator.className = "text-[8px] text-clinical-cyan font-semibold";
      setTimeout(() => {
        syncIndicator.textContent = "SYNCED";
        syncIndicator.className = "text-[8px] text-emerald-700 font-semibold";
      }, 700);
    }
  }

  function recalcPatientBSA() {
    const w = parseFloat(inWeight.value) || 74;
    const h = parseFloat(inHeight.value) || 178;
    const bsa = Math.sqrt((h * w) / 3600).toFixed(2);
    state.patient.weight = w;
    state.patient.height = h;
    state.patient.bsa = bsa;
    if (dispBsa) dispBsa.textContent = `${bsa} m²`;
    flashSync();
  }

  if (inAge) inAge.addEventListener('change', () => { state.patient.age = inAge.value; flashSync(); });
  if (inWeight) inWeight.addEventListener('input', recalcPatientBSA);
  if (inHeight) inHeight.addEventListener('input', recalcPatientBSA);

  if (selectState) {
    selectState.addEventListener('change', (e) => {
      state.patient.state = e.target.value;
      if (e.target.value === "Hypervolemic") {
        state.bloodVolume = 5.8;
      } else if (e.target.value === "Hypovolemic") {
        state.bloodVolume = 3.8;
      } else if (e.target.value === "Vasodilated") {
        state.svr = 820;
      } else {
        state.bloodVolume = 5.0;
        state.svr = 1120;
      }
      updateInputsFromState();
      sendParametersToBackend();
      flashSync();
    });
  }

  // Perturbation Sliders & Displays
  const sliderHr = document.getElementById('slider-hr');
  const sliderVol = document.getElementById('slider-vol');
  const sliderContract = document.getElementById('slider-contract');
  const sliderSvr = document.getElementById('slider-svr');

  const valHr = document.getElementById('val-hr');
  const valVol = document.getElementById('val-vol');
  const valContract = document.getElementById('val-contract');
  const valSvr = document.getElementById('val-svr');

  const statMap = document.getElementById('stat-map');
  const statCo = document.getElementById('stat-co');
  const statSv = document.getElementById('stat-sv');

  const dispLiveHr = document.getElementById('disp-live-hr');
  const dispLiveBp = document.getElementById('disp-live-bp');
  const dispLiveCo = document.getElementById('disp-live-co');

  const hudEdv = document.getElementById('hud-edv');
  const hudEsv = document.getElementById('hud-esv');
  const hudEf = document.getElementById('hud-ef');
  const hudEfStatus = document.getElementById('hud-ef-status');
  const hudContractVal = document.getElementById('hud-contract-val');
  const hudSvrVal = document.getElementById('hud-svr-val');
  const hudCpp = document.getElementById('hud-cpp');
  const hudMvo2 = document.getElementById('hud-mvo2');
  const barCpp = document.getElementById('bar-cpp');

  const valveMitral = document.getElementById('valve-mitral');
  const valveAortic = document.getElementById('valve-aortic');
  const valveTricuspid = document.getElementById('valve-tricuspid');
  const valvePulmonic = document.getElementById('valve-pulmonic');
  const gaugeContractilityCircle = document.getElementById('gauge-contractility-circle');

  // Canvases
  const canvasEcg = document.getElementById('canvas-ecg');
  const sweepLine = document.getElementById('ecg-sweep-line');
  const canvasPv = document.getElementById('canvas-pv');
  const canvasFlow = document.getElementById('canvas-pressure-flow');
  const canvas3d = document.getElementById('canvas-cardiac-3d');

  function resizeCanvas(c) {
    if (!c) return;
    const rect = c.getBoundingClientRect();
    if (c.width !== Math.floor(rect.width) || c.height !== Math.floor(rect.height)) {
      c.width = Math.floor(rect.width);
      c.height = Math.floor(rect.height);
    }
  }

  function updateInputsFromState() {
    if (sliderHr) sliderHr.value = state.hr;
    if (sliderVol) sliderVol.value = state.bloodVolume;
    if (sliderContract) sliderContract.value = state.contractility;
    if (sliderSvr) sliderSvr.value = state.svr;

    if (valHr) valHr.textContent = Math.round(state.hr);
    if (valVol) valVol.textContent = Number(state.bloodVolume).toFixed(1);
    if (valContract) valContract.textContent = Number(state.contractility).toFixed(2);
    if (valSvr) valSvr.textContent = Math.round(state.svr);
  }

  function updateTelemetryUI() {
    // Left column displays
    if (valHr) valHr.textContent = Math.round(state.hr);
    if (valVol) valVol.textContent = Number(state.bloodVolume).toFixed(1);
    if (valContract) valContract.textContent = Number(state.contractility).toFixed(2);
    if (valSvr) valSvr.textContent = Math.round(state.svr);

    const l = state.live;

    // Top summary stats
    if (statMap) statMap.textContent = Number(l.map).toFixed(1);
    if (statCo) statCo.textContent = Number(l.co).toFixed(2);
    if (statSv) statSv.textContent = Number(l.sv).toFixed(1);

    // Right Column Live Top Bar
    if (dispLiveHr) dispLiveHr.textContent = Math.round(state.hr);
    if (dispLiveBp) dispLiveBp.textContent = `${Math.round(l.sbp)}/${Math.round(l.dbp)}`;
    if (dispLiveCo) dispLiveCo.textContent = Number(l.co).toFixed(2);

    // Center HUD Displays
    if (hudEdv) hudEdv.textContent = Math.round(l.edv);
    if (hudEsv) hudEsv.textContent = Math.round(l.esv);
    if (hudEf) hudEf.textContent = Number(l.ef).toFixed(1);

    if (hudEfStatus) {
      if (l.ef < 45) {
        hudEfStatus.textContent = "LOW EF (FAIL)";
        hudEfStatus.className = "font-mono text-[7px] text-rose-700 bg-rose-50 px-1 py-0.2 rounded border border-rose-200 font-bold";
      } else if (l.ef > 75) {
        hudEfStatus.textContent = "HYPERDYNAMIC";
        hudEfStatus.className = "font-mono text-[7px] text-clinical-cyan bg-sky-50 px-1 py-0.2 rounded border border-sky-200 font-bold";
      } else {
        hudEfStatus.textContent = "NORMAL EF";
        hudEfStatus.className = "font-mono text-[7px] text-emerald-700 bg-emerald-50 px-1 py-0.2 rounded border border-emerald-200 font-bold";
      }
    }

    if (hudContractVal) hudContractVal.textContent = Number(state.contractility).toFixed(1) + 'x';
    if (hudSvrVal) hudSvrVal.textContent = Math.round(state.svr);
    if (hudCpp) hudCpp.textContent = Math.round(l.cpp);
    if (hudMvo2) hudMvo2.textContent = Number(l.mvo2).toFixed(1);

    if (gaugeContractilityCircle) {
      const pct = Math.min(100, Math.max(10, (state.contractility / 2.0) * 100));
      gaugeContractilityCircle.setAttribute('stroke-dasharray', `${pct}, 100`);
    }

    if (barCpp) {
      const cppPct = Math.min(100, Math.max(10, (l.cpp / 100) * 100));
      barCpp.style.height = `${cppPct}%`;
    }

    // Valvular indicators from real state or calculated phase
    const isMitralOpen = l.valves?.mitral?.is_open ?? (state.cyclePhase >= 0.35);
    const isAorticOpen = l.valves?.aortic?.is_open ?? (state.cyclePhase < 0.35);
    const isTricuspidOpen = l.valves?.tricuspid?.is_open ?? (state.cyclePhase >= 0.35);
    const isPulmonicOpen = l.valves?.pulmonic?.is_open ?? (state.cyclePhase < 0.35);

    if (valveMitral) {
      valveMitral.textContent = isMitralOpen ? "OPEN" : "CLOSED";
      valveMitral.className = isMitralOpen ? "text-[7px] font-bold text-emerald-700 bg-emerald-50 px-1 rounded border border-emerald-200" : "text-[7px] font-bold text-text-dim";
    }
    if (valveAortic) {
      valveAortic.textContent = isAorticOpen ? "OPEN" : "CLOSED";
      valveAortic.className = isAorticOpen ? "text-[7px] font-bold text-emerald-700 bg-emerald-50 px-1 rounded border border-emerald-200" : "text-[7px] font-bold text-text-dim";
    }
    if (valveTricuspid) {
      valveTricuspid.textContent = isTricuspidOpen ? "OPEN" : "CLOSED";
      valveTricuspid.className = isTricuspidOpen ? "text-[7px] font-bold text-emerald-700 bg-emerald-50 px-1 rounded border border-emerald-200" : "text-[7px] font-bold text-text-dim";
    }
    if (valvePulmonic) {
      valvePulmonic.textContent = isPulmonicOpen ? "OPEN" : "CLOSED";
      valvePulmonic.className = isPulmonicOpen ? "text-[7px] font-bold text-emerald-700 bg-emerald-50 px-1 rounded border border-emerald-200" : "text-[7px] font-bold text-text-dim";
    }
  }

  // =========================================================================
  // REAL WEBSOCKET CONNECTION TO SIMULATION SERVICE
  // =========================================================================
  let socket = null;
  let socketReconnectTimer = null;

  function connectSimulationWebSocket() {
    const backendBase = window.CARDIA_BACKEND || '';
    const wsProtocol = backendBase ? 'wss:' : (window.location.protocol === 'https:' ? 'wss:' : 'ws:');
    const wsHost = backendBase ? backendBase.replace(/^https?:\/\//, '') : window.location.host;
    const wsUrl = `${wsProtocol}//${wsHost}/ws/simulation`;

    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log("[CARDIA WS] Connected to live simulation engine.");
      state.isOffline = false;
      const connBadge = document.querySelector('.animate-pulse');
      if (connBadge && connBadge.parentElement) {
        connBadge.parentElement.className = "flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-50 border border-emerald-200";
      }
    };

    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "telemetry") {
          applyLiveTelemetry(msg);
        }
      } catch (err) {
        console.error("[CARDIA WS] Parse error:", err);
      }
    };

    socket.onclose = () => {
      console.warn("[CARDIA WS] Disconnected. Attempting reconnect in 1.5s...");
      state.isOffline = true;
      clearTimeout(socketReconnectTimer);
      socketReconnectTimer = setTimeout(connectSimulationWebSocket, 1500);
    };

    socket.onerror = (err) => {
      console.error("[CARDIA WS] Error:", err);
    };
  }

  function sendWsCommand(payload) {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(payload));
    }
  }

  function sendParametersToBackend() {
    sendWsCommand({
      action: "set_parameters",
      hr: state.hr,
      blood_volume: state.bloodVolume,
      contractility: state.contractility,
      svr: state.svr
    });
  }

  function applyLiveTelemetry(msg) {
    state.running = msg.running;
    state.hr = msg.heart_rate_bpm;
    state.contractility = msg.contractility;
    state.bloodVolume = msg.circulation.blood_volume_l;
    // Map backend SVR back to dyn·s/cm5 (1.0 = ~1120)
    state.svr = Math.round(msg.circulation.systemic_vascular_resistance * 1120);

    const m = msg.metrics;
    const c = msg.circulation;
    const cpp = Math.max(10, m.diastolic_bp_mmhg - c.venous_pressure_mmhg);
    const mvo2 = (m.cardiac_output_l_min * (m.systolic_bp_mmhg / 100) * 1.5);

    state.live = {
      time_s: msg.time_s,
      map: m.map_mmhg,
      sbp: m.systolic_bp_mmhg,
      dbp: m.diastolic_bp_mmhg,
      co: m.cardiac_output_l_min,
      sv: m.stroke_volume_ml,
      edv: m.edv_ml,
      esv: m.esv_ml,
      ef: m.ejection_fraction_pct,
      cpp: cpp,
      mvo2: mvo2,
      valves: msg.valves,
      chambers: msg.chambers
    };

    updateInputsFromState();
    updateTelemetryUI();
  }

  // Slider bindings -> send to real simulation
  let sliderDebounce = null;
  function onSliderChange() {
    clearTimeout(sliderDebounce);
    sliderDebounce = setTimeout(() => {
      sendParametersToBackend();
    }, 25);
    updateTelemetryUI();
  }

  if (sliderHr) {
    sliderHr.addEventListener('input', e => {
      state.hr = parseInt(e.target.value, 10);
      onSliderChange();
    });
  }
  if (sliderVol) {
    sliderVol.addEventListener('input', e => {
      state.bloodVolume = parseFloat(e.target.value);
      onSliderChange();
    });
  }
  if (sliderContract) {
    sliderContract.addEventListener('input', e => {
      state.contractility = parseFloat(e.target.value);
      onSliderChange();
    });
  }
  if (sliderSvr) {
    sliderSvr.addEventListener('input', e => {
      state.svr = parseInt(e.target.value, 10);
      onSliderChange();
    });
  }

  const btnResetSliders = document.getElementById('btn-reset-sliders');
  if (btnResetSliders) {
    btnResetSliders.addEventListener('click', () => {
      state.hr = 74;
      state.bloodVolume = 5.0;
      state.contractility = 1.0;
      state.svr = 1120;
      updateInputsFromState();
      sendParametersToBackend();
      updateTelemetryUI();
    });
  }

  // Presets
  const presetBtns = document.querySelectorAll('.preset-btn');
  presetBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const p = btn.getAttribute('data-preset');
      if (p === 'hemorrhage') {
        state.bloodVolume = 3.25;
        state.hr = 120;
        state.svr = 1680;
        state.contractility = 1.25;
      } else if (p === 'hypertension') {
        state.svr = 1950;
        state.contractility = 1.1;
        state.bloodVolume = 5.3;
      } else if (p === 'tachycardia') {
        state.hr = 145;
        state.contractility = 1.15;
      } else if (p === 'ischemia') {
        state.contractility = 0.55;
        state.svr = 1400;
        state.hr = 95;
      }
      updateInputsFromState();
      sendParametersToBackend();
      updateTelemetryUI();
      flashSync();
    });
  });

  // Playback transport buttons -> connected to backend
  const btnRun = document.getElementById('btn-run');
  const btnPause = document.getElementById('btn-pause');
  if (btnRun) {
    btnRun.addEventListener('click', () => {
      state.running = true;
      sendWsCommand({ action: "run" });
      btnRun.className = "py-1 rounded bg-emerald-600 border border-emerald-600 text-white font-mono text-[10px] font-bold uppercase flex items-center justify-center gap-1 transition-colors shadow-xs";
      if (btnPause) btnPause.className = "py-1 rounded bg-white border border-surface-border hover:bg-slate-50 text-text-muted font-mono text-[10px] uppercase flex items-center justify-center gap-1 transition-colors shadow-xs";
    });
  }
  if (btnPause) {
    btnPause.addEventListener('click', () => {
      state.running = false;
      sendWsCommand({ action: "pause" });
      btnPause.className = "py-1 rounded bg-rose-600 border border-rose-600 text-white font-mono text-[10px] font-bold uppercase flex items-center justify-center gap-1 transition-colors shadow-xs";
      if (btnRun) btnRun.className = "py-1 rounded bg-white border border-surface-border hover:bg-slate-50 text-text-muted font-mono text-[10px] uppercase flex items-center justify-center gap-1 transition-colors shadow-xs";
    });
  }

  // Simulation Speeds -> connected to backend
  const speedBtns = document.querySelectorAll('.speed-btn');
  speedBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      speedBtns.forEach(b => {
        b.className = "speed-btn px-1.5 py-0.5 rounded text-[8px] font-mono bg-white border border-surface-border text-text-muted hover:text-text-primary";
      });
      btn.className = "speed-btn px-1.5 py-0.5 rounded text-[8px] font-mono bg-clinical-teal text-white font-bold";
      state.speed = parseFloat(btn.getAttribute('data-speed'));
      sendWsCommand({ action: "set_speed", speed: state.speed });
    });
  });

  // Reset Patient -> connected to backend
  const btnResetPatient = document.getElementById('btn-reset-patient');
  if (btnResetPatient) {
    btnResetPatient.addEventListener('click', () => {
      state.hr = 74;
      state.bloodVolume = 5.0;
      state.contractility = 1.0;
      state.svr = 1120;
      state.speed = 1.0;
      state.running = true;
      state.patient = { sex: "MALE", age: 48, weight: 74, height: 178, bsa: 1.91, state: "Euvolemic" };
      if (inAge) inAge.value = 48;
      if (inWeight) inWeight.value = 74;
      if (inHeight) inHeight.value = 178;
      if (dispBsa) dispBsa.textContent = "1.91 m²";
      if (selectState) selectState.value = "Euvolemic";
      sexBtns.forEach(b => {
        if (b.getAttribute('data-sex') === "MALE") {
          b.className = "px-2 py-0.5 rounded bg-clinical-cyan text-white font-bold transition-all sex-btn";
        } else {
          b.className = "px-2 py-0.5 rounded text-text-dim hover:text-text-primary transition-all sex-btn";
        }
      });
      sendWsCommand({ action: "reset" });
      updateInputsFromState();
      updateTelemetryUI();
      flashSync();
    });
  }

  // Drawers & Modals
  const drawerAskWhy = document.getElementById('drawer-ask-why');
  const btnOpenAskWhy = document.getElementById('btn-open-ask-why');
  const btnCloseAskWhy = document.getElementById('btn-close-ask-why');
  const btnToggleAiErr = document.getElementById('btn-toggle-ai-err');
  const aiErrorBanner = document.getElementById('ai-error-banner');

  if (btnOpenAskWhy) btnOpenAskWhy.addEventListener('click', () => drawerAskWhy.classList.remove('translate-x-full'));
  if (btnCloseAskWhy) btnCloseAskWhy.addEventListener('click', () => drawerAskWhy.classList.add('translate-x-full'));
  if (btnToggleAiErr) {
    btnToggleAiErr.addEventListener('click', () => {
      state.aiOffline = !state.aiOffline;
      if (state.aiOffline) {
        aiErrorBanner.classList.remove('hidden');
        btnToggleAiErr.textContent = 'RESTORE SERVICE';
      } else {
        aiErrorBanner.classList.add('hidden');
        btnToggleAiErr.textContent = 'SIMULATE FALLBACK';
      }
    });
  }

  const modalFork = document.getElementById('modal-fork');
  const btnOpenFork = document.getElementById('btn-open-fork');
  const btnCloseFork = document.getElementById('btn-close-fork');
  const btnCancelFork = document.getElementById('btn-cancel-fork');
  const btnCommitFork = document.getElementById('btn-commit-fork');

  function hideFork() {
    if (modalFork) {
      modalFork.classList.add('hidden');
      modalFork.classList.remove('flex');
    }
  }
  if (btnOpenFork) btnOpenFork.addEventListener('click', () => {
    if (modalFork) {
      modalFork.classList.remove('hidden');
      modalFork.classList.add('flex');
    }
  });
  if (btnCloseFork) btnCloseFork.addEventListener('click', hideFork);
  if (btnCancelFork) btnCancelFork.addEventListener('click', hideFork);
  if (btnCommitFork) {
    btnCommitFork.addEventListener('click', () => {
      state.bloodVolume = 3.25;
      state.hr = 128;
      state.contractility = 1.3;
      state.svr = 1750;
      updateInputsFromState();
      sendParametersToBackend();
      updateTelemetryUI();
      hideFork();
    });
  }

  // =========================================================================
  // REAL ML PARAMETER INFERENCE MODAL INTEGRATION
  // =========================================================================
  const modalMl = document.getElementById('modal-ml');
  const btnOpenMl = document.getElementById('btn-open-ml');
  const btnCloseMl = document.getElementById('btn-close-ml');
  const btnDismissMl = document.getElementById('btn-dismiss-ml');
  const btnRunMl = document.getElementById('btn-run-ml');

  function hideMlModal() {
    if (modalMl) {
      modalMl.classList.add('hidden');
      modalMl.classList.remove('flex');
    }
  }

  function showMlModal() {
    if (modalMl) {
      modalMl.classList.remove('hidden');
      modalMl.classList.add('flex');
      // populate observables
      document.getElementById('ml-obs-hr').textContent = Math.round(state.hr);
      document.getElementById('ml-obs-sbp').textContent = Math.round(state.live.sbp);
      document.getElementById('ml-obs-dbp').textContent = Math.round(state.live.dbp);
      document.getElementById('ml-obs-edv').textContent = Math.round(state.live.edv);
      document.getElementById('ml-obs-esv').textContent = Math.round(state.live.esv);
      document.getElementById('ml-status-text').textContent = "Ready to infer parameters.";
    }
  }

  if (btnOpenMl) btnOpenMl.addEventListener('click', showMlModal);
  if (btnCloseMl) btnCloseMl.addEventListener('click', hideMlModal);
  if (btnDismissMl) btnDismissMl.addEventListener('click', hideMlModal);

  if (btnRunMl) {
    btnRunMl.addEventListener('click', async () => {
      const statusEl = document.getElementById('ml-status-text');
      statusEl.textContent = "Running neural latent inference...";
      btnRunMl.disabled = true;

      try {
        const resp = await fetch((window.CARDIA_BACKEND || '') + '/api/ml/predict', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            heart_rate: state.hr,
            systolic_bp: state.live.sbp,
            diastolic_bp: state.live.dbp,
            edv: state.live.edv,
            esv: state.live.esv
          })
        });

        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}`);
        }

        const data = await resp.json();
        const p = data.inferred_parameters;
        const cur = data.current_simulation_parameters;

        document.getElementById('ml-inf-vol').innerHTML = `${p.blood_volume_l.toFixed(2)} <span class="text-xs font-normal">L</span>`;
        document.getElementById('ml-sim-vol').textContent = `Sim true: ${cur.blood_volume_l.toFixed(2)} L`;

        document.getElementById('ml-inf-contract').innerHTML = `${p.contractility.toFixed(2)} <span class="text-xs font-normal">x</span>`;
        document.getElementById('ml-sim-contract').textContent = `Sim true: ${cur.contractility.toFixed(2)} x`;

        // ML output is relative SVR (~1.0)
        const inferredSvrDyn = Math.round(p.systemic_vascular_resistance * 1120);
        const simSvrDyn = Math.round(cur.systemic_vascular_resistance * 1120);
        document.getElementById('ml-inf-svr').innerHTML = `${inferredSvrDyn} <span class="text-xs font-normal">dyn·s</span>`;
        document.getElementById('ml-sim-svr').textContent = `Sim true: ${simSvrDyn}`;

        statusEl.textContent = "Parameters inferred successfully via CardiaPredictor.";
      } catch (err) {
        statusEl.textContent = `Inference failed: ${err.message}`;
      } finally {
        btnRunMl.disabled = false;
      }
    });
  }

  // =========================================================================
  // REAL RAG ASK-WHY INTEGRATION
  // =========================================================================
  const ragInput = document.getElementById('rag-input-text');
  const btnSendRag = document.getElementById('btn-send-rag');
  const ragChatMessages = document.getElementById('rag-chat-messages');

  async function handleSendRag() {
    if (!ragInput) return;
    const question = ragInput.value.trim();
    if (!question) return;

    if (state.aiOffline) {
      alert("AI Explanation Core is currently in simulated fallback mode.");
      return;
    }

    // Append user bubble
    const userMsg = document.createElement('div');
    userMsg.className = "flex flex-col gap-1 items-end";
    userMsg.innerHTML = `
      <span class="text-[8px] text-text-dim font-medium">Investigator (Just now)</span>
      <div class="bg-white border border-surface-border rounded-lg p-2.5 max-w-[90%] text-text-primary text-[11px] shadow-xs">
        ${escapeHtml(question)}
      </div>
    `;
    ragChatMessages.appendChild(userMsg);
    ragInput.value = '';

    // Append loading bubble
    const loadingMsg = document.createElement('div');
    loadingMsg.className = "flex flex-col gap-1 items-start";
    loadingMsg.innerHTML = `
      <span class="text-[8px] text-emerald-700 font-bold flex items-center gap-1">
        <span class="w-1.5 h-1.5 rounded-full bg-clinical-emerald animate-ping"></span> Retrieving physiological evidence...
      </span>
    `;
    ragChatMessages.appendChild(loadingMsg);
    ragChatMessages.scrollTop = ragChatMessages.scrollHeight;

    try {
      const resp = await fetch((window.CARDIA_BACKEND || '') + '/api/rag/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: question, include_live_state: true })
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();

      loadingMsg.remove();

      const aiMsg = document.createElement('div');
      aiMsg.className = "flex flex-col gap-1 items-start";
      
      const sourceList = data.sources && data.sources.length > 0
        ? data.sources.map(s => s.reference || s.source_file || "Guyton Physiology").join(', ')
        : "Guyton & Hall / Cardiovascular Dynamics";

      aiMsg.innerHTML = `
        <span class="text-[8px] text-emerald-700 font-bold flex items-center gap-1">
          <span class="w-1.5 h-1.5 rounded-full bg-clinical-emerald"></span> Grounded Hemodynamic Rationale
        </span>
        <div class="bg-white border border-surface-border rounded-lg p-3 max-w-[95%] text-text-primary flex flex-col gap-2 text-[11px] leading-relaxed shadow-sm">
          <p class="text-slate-700 whitespace-pre-line">${escapeHtml(data.explanation)}</p>
          <div class="pt-1.5 flex items-center justify-between text-[9px] text-text-dim border-t border-surface-border font-medium">
            <span>Ref: ${escapeHtml(sourceList)}</span>
            <span class="text-emerald-700 font-semibold">Confidence: ${(data.confidence * 100).toFixed(1)}%</span>
          </div>
        </div>
      `;
      ragChatMessages.appendChild(aiMsg);
      ragChatMessages.scrollTop = ragChatMessages.scrollHeight;
    } catch (err) {
      loadingMsg.innerHTML = `
        <span class="text-[8px] text-rose-700 font-bold">Error retrieving explanation: ${escapeHtml(err.message)}</span>
      `;
    }
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  if (btnSendRag) btnSendRag.addEventListener('click', handleSendRag);
  if (ragInput) {
    ragInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') handleSendRag();
    });
  }

  // =========================================================================
  // 3D CARDIAC TWIN CANVAS ENGINE (RENDERED WIREFRAME + MYOCARDIUM BEAT)
  // =========================================================================
  let isDragging3D = false;
  let prevMouseX = 0;
  let prevMouseY = 0;

  if (canvas3d) {
    canvas3d.addEventListener('mousedown', (e) => {
      isDragging3D = true;
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;
    });
    window.addEventListener('mouseup', () => { isDragging3D = false; });
    window.addEventListener('mousemove', (e) => {
      if (!isDragging3D) return;
      const dx = e.clientX - prevMouseX;
      const dy = e.clientY - prevMouseY;
      state.viewRotY += dx * 0.01;
      state.viewRotX = Math.max(-1.2, Math.min(1.2, state.viewRotX + dy * 0.01));
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;
    });
    canvas3d.addEventListener('wheel', (e) => {
      state.viewZoom = Math.max(0.6, Math.min(2.0, state.viewZoom - e.deltaY * 0.001));
      e.preventDefault();
    }, { passive: false });
  }

  function drawCardiac3D(ctx, width, height, pulseScale) {
    ctx.clearRect(0, 0, width, height);
    const cx = width / 2;
    const cy = height / 2;
    const scale = Math.min(width, height) * 0.32 * state.viewZoom * pulseScale;

    const rotX = state.viewRotX;
    const rotY = state.viewRotY;

    const latCount = 14;
    const lonCount = 16;
    const points = [];

    for (let i = 0; i <= latCount; i++) {
      const theta = (i / latCount) * Math.PI;
      const ring = [];
      for (let j = 0; j < lonCount; j++) {
        const phi = (j / lonCount) * Math.PI * 2;
        const r = (1 - Math.sin(theta) * 0.25) * (1 + 0.15 * Math.sin(phi * 2));
        let x = r * Math.sin(theta) * Math.cos(phi) * 0.85;
        let y = -r * Math.cos(theta) * 1.1 + (Math.sin(theta) * 0.15);
        let z = r * Math.sin(theta) * Math.sin(phi) * 0.85;

        let rx = x * Math.cos(rotY) + z * Math.sin(rotY);
        let rz = -x * Math.sin(rotY) + z * Math.cos(rotY);

        let ry = y * Math.cos(rotX) - rz * Math.sin(rotX);
        rz = y * Math.sin(rotX) + rz * Math.cos(rotX);

        const fov = 3.5;
        const pers = fov / (fov + rz);
        ring.push({
          px: cx + rx * scale * pers,
          py: cy + ry * scale * pers,
          depth: rz
        });
      }
      points.push(ring);
    }

    ctx.strokeStyle = 'rgba(2, 132, 199, 0.22)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= latCount; i++) {
      ctx.beginPath();
      for (let j = 0; j < lonCount; j++) {
        const pt = points[i][j];
        if (j === 0) ctx.moveTo(pt.px, pt.py);
        else ctx.lineTo(pt.px, pt.py);
      }
      ctx.closePath();
      ctx.stroke();
    }

    for (let j = 0; j < lonCount; j++) {
      ctx.beginPath();
      for (let i = 0; i <= latCount; i++) {
        const pt = points[i][j];
        if (i === 0) ctx.moveTo(pt.px, pt.py);
        else ctx.lineTo(pt.px, pt.py);
      }
      ctx.stroke();
    }

    const grad = ctx.createRadialGradient(cx, cy, 10, cx, cy, scale * 0.8);
    grad.addColorStop(0, 'rgba(2, 132, 199, 0.12)');
    grad.addColorStop(0.7, 'rgba(0, 97, 148, 0.04)');
    grad.addColorStop(1, 'rgba(255, 255, 255, 0)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(cx, cy, scale * 0.75, 0, Math.PI * 2);
    ctx.fill();

    const topPt = points[0][0];
    ctx.strokeStyle = '#0284c7';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(topPt.px, topPt.py - 14, 12 * state.viewZoom, 0, Math.PI * 2);
    ctx.stroke();
  }

  // ==========================================
  // REAL-TIME CANVAS CHARTS (ECG, PV, FLOW)
  // ==========================================
  function getEcgSample(t) {
    if (t < 0.15) return 0;
    if (t < 0.22) {
      const p = (t - 0.15) / 0.07;
      return Math.sin(p * Math.PI) * 0.18;
    }
    if (t < 0.28) return 0;
    if (t < 0.30) return -0.16;
    if (t < 0.35) {
      const r = (t - 0.30) / 0.05;
      return Math.sin(r * Math.PI) * 1.0;
    }
    if (t < 0.38) return -0.28;
    if (t < 0.45) return 0;
    if (t < 0.65) {
      const tw = (t - 0.45) / 0.20;
      return Math.sin(tw * Math.PI) * 0.32;
    }
    return 0;
  }

  const ecgHistory = new Float32Array(300);
  let ecgIndex = 0;

  function renderWaveforms(timestamp) {
    if (!state.running) {
      requestAnimationFrame(renderWaveforms);
      return;
    }

    const dt = (timestamp - state.lastFrameTime) / 1000;
    state.lastFrameTime = timestamp;

    const beatDuration = 60 / (Math.max(30, state.hr) * Math.max(0.2, state.speed));
    state.cyclePhase = (state.cyclePhase + (dt / beatDuration)) % 1.0;

    let pulseScale = 1.0;
    if (state.cyclePhase < 0.35) {
      pulseScale = 1.0 - 0.12 * Math.sin((state.cyclePhase / 0.35) * Math.PI);
    } else {
      pulseScale = 0.88 + 0.12 * Math.sin(((state.cyclePhase - 0.35) / 0.65) * Math.PI * 0.5);
    }

    // 3D Canvas
    if (canvas3d) {
      resizeCanvas(canvas3d);
      const ctx3d = canvas3d.getContext('2d');
      if (ctx3d) {
        drawCardiac3D(ctx3d, canvas3d.width, canvas3d.height, pulseScale);
      }
    }

    // 1. ECG Strip
    if (canvasEcg) {
      resizeCanvas(canvasEcg);
      const ctx = canvasEcg.getContext('2d');
      if (ctx) {
        const sample = getEcgSample(state.cyclePhase);
        const steps = Math.max(1, Math.round(dt * 120 * state.speed));
        for (let s = 0; s < steps; s++) {
          ecgHistory[ecgIndex] = sample;
          ecgIndex = (ecgIndex + 1) % ecgHistory.length;
        }

        if (sweepLine) {
          sweepLine.style.left = `${(ecgIndex / ecgHistory.length) * 100}%`;
        }

        ctx.clearRect(0, 0, canvasEcg.width, canvasEcg.height);
        ctx.lineWidth = 1.75;
        ctx.strokeStyle = '#0284c7';
        ctx.beginPath();
        const midY = canvasEcg.height * 0.65;
        const scaleX = canvasEcg.width / ecgHistory.length;
        for (let i = 0; i < ecgHistory.length; i++) {
          const y = midY - (ecgHistory[i] * (canvasEcg.height * 0.42));
          if (i === 0) ctx.moveTo(i * scaleX, y);
          else ctx.lineTo(i * scaleX, y);
        }
        ctx.stroke();
      }
    }

    // 2. PV Loop Canvas
    if (canvasPv) {
      resizeCanvas(canvasPv);
      const ctx = canvasPv.getContext('2d');
      if (ctx) {
        ctx.clearRect(0, 0, canvasPv.width, canvasPv.height);
        const l = state.live;
        const w = canvasPv.width;
        const ch = canvasPv.height;

        const sx = vol => (vol / 180) * (w - 24) + 12;
        const sy = press => ch - 10 - (press / 160) * (ch - 20);

        const edvX = sx(l.edv);
        const esvX = sx(l.esv);
        const sbpY = sy(l.sbp);
        const dbpY = sy(l.dbp);
        const edpY = sy(10);

        // Elastance line
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);
        ctx.strokeStyle = 'rgba(2, 132, 199, 0.35)';
        ctx.beginPath();
        ctx.moveTo(sx(15), sy(0));
        ctx.lineTo(esvX + 20, sbpY - 10);
        ctx.stroke();
        ctx.setLineDash([]);

        // Filled PV Area
        ctx.fillStyle = 'rgba(2, 132, 199, 0.08)';
        ctx.beginPath();
        ctx.moveTo(esvX, edpY);
        ctx.lineTo(edvX, edpY);
        ctx.lineTo(edvX, dbpY);
        ctx.bezierCurveTo((edvX + esvX)/2, sbpY - 8, esvX, sbpY, esvX, sbpY);
        ctx.lineTo(esvX, edpY);
        ctx.fill();

        // Stroke Loop
        ctx.lineWidth = 1.75;
        ctx.strokeStyle = '#0284c7';
        ctx.beginPath();
        ctx.moveTo(esvX, edpY);
        ctx.lineTo(edvX, edpY);
        ctx.lineTo(edvX, dbpY);
        ctx.bezierCurveTo((edvX + esvX)/2, sbpY - 8, esvX, sbpY, esvX, sbpY);
        ctx.lineTo(esvX, edpY);
        ctx.stroke();

        // Dynamic traveling marker
        let mx = edvX;
        let my = edpY;
        const cp = state.cyclePhase;
        if (cp < 0.15) {
          const t = cp / 0.15;
          mx = edvX;
          my = edpY + (dbpY - edpY) * t;
        } else if (cp < 0.40) {
          const t = (cp - 0.15) / 0.25;
          mx = edvX - (edvX - esvX) * t;
          my = dbpY + (sbpY - dbpY) * Math.sin(t * Math.PI);
        } else if (cp < 0.50) {
          const t = (cp - 0.40) / 0.10;
          mx = esvX;
          my = sbpY + (edpY - sbpY) * t;
        } else {
          const t = (cp - 0.50) / 0.50;
          mx = esvX + (edvX - esvX) * t;
          my = edpY;
        }

        ctx.fillStyle = '#059669';
        ctx.beginPath();
        ctx.arc(mx, my, 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    }

    // 3. Pressure & Flow Canvas
    if (canvasFlow) {
      resizeCanvas(canvasFlow);
      const ctx = canvasFlow.getContext('2d');
      if (ctx) {
        ctx.clearRect(0, 0, canvasFlow.width, canvasFlow.height);
        const l = state.live;
        const w = canvasFlow.width;
        const ch = canvasFlow.height;

        // Aortic Pressure
        ctx.lineWidth = 1.75;
        ctx.strokeStyle = '#1e293b';
        ctx.beginPath();
        for (let x = 0; x < w; x++) {
          const frac = ((x / (w * 0.6)) + state.cyclePhase) % 1.0;
          let p = 0;
          if (frac < 0.25) p = Math.sin((frac / 0.25) * Math.PI * 0.5);
          else if (frac < 0.35) p = 0.9 - 0.15 * Math.sin(((frac - 0.25) / 0.10) * Math.PI);
          else p = 0.75 * Math.exp(-(frac - 0.35) * 3.5);

          const y = (ch * 0.78) - (p * (ch * 0.55) * (l.sbp / 130));
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();

        // Flow Velocity
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = '#059669';
        ctx.beginPath();
        for (let x = 0; x < w; x++) {
          const frac = ((x / (w * 0.6)) + state.cyclePhase) % 1.0;
          let f = 0;
          if (frac < 0.28) f = Math.sin((frac / 0.28) * Math.PI);
          const y = (ch * 0.92) - (f * (ch * 0.58) * (l.co / 5.4));
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
      }
    }

    requestAnimationFrame(renderWaveforms);
  }

  // Initialize
  updateInputsFromState();
  updateTelemetryUI();
  connectSimulationWebSocket();
  requestAnimationFrame(renderWaveforms);
})();
