/**
 * CARDIA Heart3D — Three.js GLB Integration Module with Fixed Anatomical Annotations
 * ===================================================================================
 * Loads the beating heart GLB model and drives its animation from the existing
 * SimulationState telemetry pipeline.
 *
 * Provides fixed 3D anatomical annotations for the 8 key cardiovascular structures:
 * 1. Right Atrium
 * 2. Right Ventricle
 * 3. Left Atrium
 * 4. Left Ventricle
 * 5. Mitral Valve
 * 6. Aortic Valve
 * 7. Aorta
 * 8. Pulmonary Artery
 *
 * Each annotation is anchored to a specific 3D position on the heart in world space.
 * When the heart rotates, zooms, or animates, the anchors track accurately in screen space.
 *
 * Features:
 * - Fixed 3D anchor points projected dynamically every frame
 * - Screen-space leader lines drawn cleanly via SVG overlay
 * - Live chamber/valve hemodynamic telemetry tags
 * - Interactive hover focus state and detail tooltip
 * - Global hide/show toggle with smooth fade
 * - Collision / boundary prevention within the viewport
 *
 * The existing window.__CARDIA_STATE remains the single source of truth.
 */

class CardiaHeart3D {
  constructor(canvasId) {
    this.canvasId = canvasId;
    this.canvas = null;
    this.renderer = null;
    this.scene = null;
    this.camera = null;
    this.model = null;
    this.mixer = null;
    this.animAction = null;
    this.clock = new THREE.Clock();

    // Lighting references
    this.ambientLight = null;
    this.mainLight = null;
    this.fillLight = null;
    this.rimLight = null;

    // Joint mapping for valve/chamber node anchoring
    this.joints = {};

    // State
    this.isLoaded = false;
    this.lastHR = 74;
    this.disposed = false;

    // Existing drag state integration
    this._isDragging = false;
    this._prevX = 0;
    this._prevY = 0;

    // Orbit target and spherical coords
    this._theta = -0.4;   // matches viewRotY default
    this._phi = 1.37;     // ~78° (slight overhead)
    this._radius = 3.2;
    this._target = null;

    // Glow meshes for visual feedback
    this._innerGlow = null;

    // Annotations system
    this.showAnnotations = false;
    this.annotationElements = [];
    this.annotationsContainer = null;
    this.annotationsSvg = null;
    this.annotationsDef = [];
    this.activeHoverId = null;

    // Reusable projection vector
    this._tempVec = null;
  }

  /**
   * Initialize the Three.js scene, load the GLB, and start the render loop.
   */
  async init() {
    this.canvas = document.getElementById(this.canvasId);
    if (!this.canvas) {
      console.error('[CardiaHeart3D] Canvas element not found:', this.canvasId);
      return;
    }

    this._tempVec = new THREE.Vector3();

    // --- Scene ---
    this.scene = new THREE.Scene();
    this.scene.background = null;

    // Orbit target
    this._target = new THREE.Vector3(0, 0.3, 0);

    // --- Camera ---
    const rect = this.canvas.getBoundingClientRect();
    this.camera = new THREE.PerspectiveCamera(
      40, (rect.width || 500) / (rect.height || 700), 0.01, 100
    );
    this._updateCameraFromSpherical();

    // --- Renderer ---
    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance'
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(rect.width, rect.height, false);
    if (this.renderer.outputColorSpace !== undefined) {
      this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    } else {
      this.renderer.outputEncoding = THREE.sRGBEncoding;
    }
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.2;

    // --- Lighting (clinical, clean) ---
    this.ambientLight = new THREE.AmbientLight(0xc8e0f0, 0.7);
    this.scene.add(this.ambientLight);

    this.mainLight = new THREE.DirectionalLight(0xffffff, 1.8);
    this.mainLight.position.set(2, 4, 3);
    this.mainLight.castShadow = false;
    this.scene.add(this.mainLight);

    this.fillLight = new THREE.DirectionalLight(0x89b4d6, 0.6);
    this.fillLight.position.set(-3, 1, -2);
    this.scene.add(this.fillLight);

    this.rimLight = new THREE.DirectionalLight(0xaaccee, 0.4);
    this.rimLight.position.set(0, -2, 4);
    this.scene.add(this.rimLight);

    const hemiLight = new THREE.HemisphereLight(0xddeeff, 0x8899aa, 0.3);
    this.scene.add(hemiLight);

    // --- Input handling ---
    this._bindInputs();

    // --- Setup DOM Overlays for Annotations ---
    // this._initAnnotationOverlays();

    // --- Load GLB ---
    await this._loadGLB();

    // --- Start render loop ---
    this._animate();

    console.log('[CardiaHeart3D] Initialized successfully with fixed 3D annotations.');
  }

  /**
   * Load the heart GLB model
   */
  _loadGLB() {
    return new Promise((resolve, reject) => {
      const LoaderClass = THREE.GLTFLoader || (THREE.Loaders && THREE.Loaders.GLTFLoader);
      if (!LoaderClass) {
        const err = new Error('THREE.GLTFLoader not found. Check CDN script ordering.');
        this._showLoadError('3D Loader Unavailable', err.message);
        reject(err);
        return;
      }
      const loader = new LoaderClass();

      // Dynamic asset base resolution (works on localhost, custom origins, and reverse proxies)
      const CARDIA_ASSET_BASE =
        document.querySelector('meta[name="cardia-asset-base"]')?.content
        || '/static';
      const HEART_MODEL_URL = `${CARDIA_ASSET_BASE}/assets/heart.glb`;

      loader.load(
        HEART_MODEL_URL,
        (gltf) => {
          this.model = gltf.scene;

          // Scale and position to fit viewport
          const box = new THREE.Box3().setFromObject(this.model);
          const size = box.getSize(new THREE.Vector3());
          const center = box.getCenter(new THREE.Vector3());
          const maxDim = Math.max(size.x, size.y, size.z);
          const scaleFactor = 2.0 / maxDim;

          this.model.scale.setScalar(scaleFactor);
          this.model.position.sub(center.multiplyScalar(scaleFactor));
          this.model.position.y += 0.3;

          // Traverse materials and capture joints
          this.model.traverse((child) => {
            if (child.isMesh) {
              child.material = child.material.clone();
              if (child.material.isMeshStandardMaterial) {
                child.material.roughness = 0.55;
                child.material.metalness = 0.05;
              }
              child.frustumCulled = false;
            }

            if (child.isBone || child.name.includes('jnt')) {
              this.joints[child.name] = child;
            }
          });

          this.scene.add(this.model);

          // Setup animation
          if (gltf.animations && gltf.animations.length > 0) {
            this.mixer = new THREE.AnimationMixer(this.model);
            const clip = gltf.animations[0];
            this.animAction = this.mixer.clipAction(clip);
            this.animAction.play();
            this._syncAnimationToHR(74);
          }

          this.isLoaded = true;

          // Create glow overlay
          this._createGlowOverlays();

          // Initialize anatomical anchor definitions now that model & joints exist
          this._setupAnatomicalAnchors();

          resolve();
        },
        (progress) => {
          const pct = progress.total > 0
            ? Math.round((progress.loaded / progress.total) * 100)
            : '??';
          console.log(`[CardiaHeart3D] Loading GLB from ${HEART_MODEL_URL}... ${pct}%`);
        },
        (error) => {
          console.error('[CARDIA Heart3D] Failed to load heart model:', HEART_MODEL_URL, error);
          this._showLoadError('3D heart unavailable', 'Unable to load heart model.');
          reject(error);
        }
      );
    });
  }

  /**
   * Display non-blocking clinical diagnostic message in 3D viewport if model fails
   */
  _showLoadError(title, subtitle) {
    if (!this.canvas) return;
    const parent = this.canvas.parentElement;
    if (!parent) return;

    let errEl = document.getElementById('cardia-3d-load-error');
    if (!errEl) {
      errEl = document.createElement('div');
      errEl.id = 'cardia-3d-load-error';
      errEl.className = 'absolute inset-0 z-10 flex flex-col items-center justify-center pointer-events-none p-4 text-center';
      errEl.innerHTML = `
        <div class="bg-white/95 backdrop-blur border border-rose-200 rounded-lg p-3 shadow-md font-mono max-w-xs pointer-events-auto">
          <div class="flex items-center justify-center gap-1.5 text-rose-600 mb-1">
            <span class="material-symbols-outlined text-[18px]">warning</span>
            <span class="text-xs font-bold" id="cardia-3d-err-title">${title}</span>
          </div>
          <p class="text-[10px] text-text-dim leading-snug" id="cardia-3d-err-sub">${subtitle}</p>
        </div>
      `;
      parent.appendChild(errEl);
    }
  }

  /**
   * Defines the 8 anatomical structures with their 3D anchor points.
   * Uses joints when available so anchors automatically follow skeletal beating motion,
   * with fallback to calibrated 3D world-space coordinates.
   */
  _setupAnatomicalAnchors() {
    this.annotationsDef = [
      {
        id: "rightAtrium",
        label: "Right Atrium",
        subtitle: "Deoxygenated venous inflow (SVC/IVC)",
        jointName: "right_atrium_jnt.6",
        fallbackAnchor: new THREE.Vector3(-0.55, 0.48, 0.41),
        screenSide: "left",
        offset: { x: -75, y: -25 },
        color: "#0284c7",
        badge: "RA",
        liveKey: "right_atrium"
      },
      {
        id: "rightVentricle",
        label: "Right Ventricle",
        subtitle: "Pulmonary pump (low pressure)",
        jointName: "right_tricuspid_valve_jnt.24",
        fallbackAnchor: new THREE.Vector3(-0.35, 0.05, 0.32),
        screenSide: "left",
        offset: { x: -80, y: 35 },
        color: "#0284c7",
        badge: "RV",
        liveKey: "right_ventricle"
      },
      {
        id: "leftAtrium",
        label: "Left Atrium",
        subtitle: "Oxygenated pulmonary inflow",
        jointName: "left_atrium_jnt.13",
        fallbackAnchor: new THREE.Vector3(0.38, 0.67, 0.39),
        screenSide: "right",
        offset: { x: 75, y: -30 },
        color: "#dc2626",
        badge: "LA",
        liveKey: "left_atrium"
      },
      {
        id: "leftVentricle",
        label: "Left Ventricle",
        subtitle: "Systemic high-pressure chamber",
        jointName: "cardiac_muscle_jnt.7",
        fallbackAnchor: new THREE.Vector3(0.12, -0.32, 0.30),
        screenSide: "right",
        offset: { x: 80, y: 40 },
        color: "#dc2626",
        badge: "LV",
        liveKey: "left_ventricle"
      },
      {
        id: "mitralValve",
        label: "Mitral Valve",
        subtitle: "Bicuspid AV valve (LA → LV)",
        jointName: "left_mitral_valve_jnt.15",
        fallbackAnchor: new THREE.Vector3(0.35, 0.28, 0.30),
        screenSide: "right",
        offset: { x: 85, y: 5 },
        color: "#059669",
        badge: "MV",
        liveValve: "mitral"
      },
      {
        id: "aorticValve",
        label: "Aortic Valve",
        subtitle: "Semilunar outflow valve (LV → Ao)",
        jointName: "aortic_valve_02_jnt.17",
        fallbackAnchor: new THREE.Vector3(0.12, 0.28, 0.33),
        screenSide: "right",
        offset: { x: 70, y: -70 },
        color: "#059669",
        badge: "AV",
        liveValve: "aortic"
      },
      {
        id: "aorta",
        label: "Aorta",
        subtitle: "Systemic arterial root & arch",
        jointName: null,
        fallbackAnchor: new THREE.Vector3(0.08, 0.98, 0.18),
        screenSide: "right",
        offset: { x: 65, y: -65 },
        color: "#b91c1c",
        badge: "AO",
        liveCirc: "aortic_pressure_mmhg"
      },
      {
        id: "pulmonaryArtery",
        label: "Pulmonary Artery",
        subtitle: "Deoxygenated outflow to lungs",
        jointName: "right_pulmonary_valve_jnt.9",
        fallbackAnchor: new THREE.Vector3(-0.18, 0.72, 0.34),
        screenSide: "left",
        offset: { x: -75, y: -55 },
        color: "#2563eb",
        badge: "PA",
        liveCirc: "pulmonary_artery_pressure_mmhg"
      }
    ];

    this._createAnnotationDOMElements();
  }

  /**
   * Initializes overlay container and SVG canvas on top of the 3D canvas
   */
  _initAnnotationOverlays() {
    const parent = this.canvas.parentElement;
    if (!parent) return;

    // Ensure relative positioning
    if (getComputedStyle(parent).position === 'static') {
      parent.style.position = 'relative';
    }

    // HTML elements container
    const container = document.createElement('div');
    container.id = 'cardia-annotations-container';
    container.className = 'absolute inset-0 pointer-events-none z-20 overflow-hidden';
    container.style.transition = 'opacity 0.25s ease-in-out';
    parent.appendChild(container);
    this.annotationsContainer = container;

    // SVG canvas for leader connector lines
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.id = 'cardia-annotations-svg';
    svg.setAttribute('class', 'absolute inset-0 w-full h-full pointer-events-none z-15');
    svg.style.overflow = 'visible';
    parent.appendChild(svg);
    this.annotationsSvg = svg;

    // Append toggle button to center HUD or bottom overlay
    this._injectToggleButton();
  }

  /**
   * Create DOM cards, anchor dots, and SVG leader lines for all 8 annotations
   */
  _createAnnotationDOMElements() {
    if (!this.annotationsContainer || !this.annotationsSvg) return;

    this.annotationsContainer.innerHTML = '';
    this.annotationsSvg.innerHTML = '';
    this.annotationElements = [];

    // Create defs in SVG for marker glow / gradients
    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    defs.innerHTML = `
      <linearGradient id="line-cyan-grad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#0284c7" stop-opacity="0.9"/>
        <stop offset="100%" stop-color="#38bdf8" stop-opacity="0.3"/>
      </linearGradient>
      <linearGradient id="line-rose-grad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#dc2626" stop-opacity="0.9"/>
        <stop offset="100%" stop-color="#f87171" stop-opacity="0.3"/>
      </linearGradient>
      <linearGradient id="line-green-grad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#059669" stop-opacity="0.9"/>
        <stop offset="100%" stop-color="#34d399" stop-opacity="0.3"/>
      </linearGradient>
    `;
    this.annotationsSvg.appendChild(defs);

    this.annotationsDef.forEach((def, index) => {
      // 1. Anchor 3D pin dot (at projected anchor position)
      const pin = document.createElement('div');
      pin.className = 'absolute pointer-events-none transition-transform duration-75';
      pin.style.width = '12px';
      pin.style.height = '12px';
      pin.style.marginLeft = '-6px';
      pin.style.marginTop = '-6px';
      pin.innerHTML = `
        <div class="relative w-full h-full flex items-center justify-center">
          <div class="absolute inset-0 rounded-full animate-ping opacity-60" style="background-color: ${def.color};"></div>
          <div class="w-2.5 h-2.5 rounded-full border border-white shadow-sm" style="background-color: ${def.color};"></div>
        </div>
      `;
      this.annotationsContainer.appendChild(pin);

      // 2. SVG Line
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('fill', 'none');
      path.setAttribute('stroke', def.color);
      path.setAttribute('stroke-width', '1.2');
      path.setAttribute('stroke-dasharray', '2 2');
      path.setAttribute('opacity', '0.75');
      this.annotationsSvg.appendChild(path);

      // 3. Floating Card
      const card = document.createElement('div');
      card.className = 'absolute pointer-events-auto cursor-pointer transition-all duration-100 rounded border bg-white/95 backdrop-blur shadow-md px-2 py-1 font-mono hover:scale-105 hover:shadow-lg hover:border-clinical-cyan hover:z-30';
      card.style.borderColor = '#e2e8f0';
      card.style.fontSize = '9px';
      card.style.minWidth = '110px';
      card.style.maxWidth = '160px';
      card.style.userSelect = 'none';

      card.innerHTML = `
        <div class="flex items-center justify-between gap-1 pb-0.5 border-b border-surface-border">
          <div class="flex items-center gap-1 font-bold text-text-primary">
            <span class="w-1.5 h-1.5 rounded-full" style="background-color: ${def.color};"></span>
            <span class="tracking-tight">${def.label}</span>
          </div>
          <span class="px-1 py-0.2 rounded text-[7px] font-bold text-white uppercase" style="background-color: ${def.color};">${def.badge}</span>
        </div>
        <div class="flex items-center justify-between pt-0.5 text-[8px]">
          <span class="text-text-dim truncate">${def.subtitle}</span>
          <span class="font-bold text-text-primary ml-1" id="ann-val-${def.id}">--</span>
        </div>
      `;

      // Hover interactivity
      card.addEventListener('mouseenter', () => {
        this.activeHoverId = def.id;
        path.setAttribute('stroke-width', '2.2');
        path.setAttribute('stroke-dasharray', 'none');
        path.setAttribute('opacity', '1.0');
        pin.style.transform = 'scale(1.4)';
      });

      card.addEventListener('mouseleave', () => {
        this.activeHoverId = null;
        path.setAttribute('stroke-width', '1.2');
        path.setAttribute('stroke-dasharray', '2 2');
        path.setAttribute('opacity', '0.75');
        pin.style.transform = 'scale(1.0)';
      });

      this.annotationsContainer.appendChild(card);

      this.annotationElements.push({
        def,
        pin,
        path,
        card,
        valEl: card.querySelector(`#ann-val-${def.id}`)
      });
    });
  }

  /**
   * Adds the Annotations toggle button cleanly in the center header or floating HUD
   */
  _injectToggleButton() {
    const existingBtn = document.getElementById('btn-toggle-annotations');
    if (existingBtn) {
      existingBtn.addEventListener('click', () => {
        this.toggleAnnotations();
      });
      return;
    }

    const section = this.canvas.closest('section');
    if (!section) return;

    const toggleBtn = document.createElement('button');
    toggleBtn.id = 'btn-toggle-annotations';
    toggleBtn.type = 'button';
    toggleBtn.className = 'absolute top-2 right-44 z-30 pointer-events-auto bg-white/95 backdrop-blur border border-surface-border px-2 py-0.5 rounded font-mono text-[9px] font-semibold text-text-primary hover:text-clinical-cyan hover:border-clinical-cyan flex items-center gap-1 shadow-sm transition-all';
    toggleBtn.innerHTML = `
      <span class="material-symbols-outlined text-[13px] text-clinical-cyan">label</span>
      <span id="txt-toggle-annotations">Labels: ON</span>
    `;

    toggleBtn.addEventListener('click', () => {
      this.toggleAnnotations();
    });

    section.appendChild(toggleBtn);
  }

  /**
   * Toggle annotations visibility
   */
  toggleAnnotations(forceState) {
    if (typeof forceState === 'boolean') {
      this.showAnnotations = forceState;
    } else {
      this.showAnnotations = !this.showAnnotations;
    }

    if (this.annotationsContainer) {
      this.annotationsContainer.style.opacity = this.showAnnotations ? '1' : '0';
      this.annotationsContainer.style.pointerEvents = this.showAnnotations ? 'auto' : 'none';
    }
    if (this.annotationsSvg) {
      this.annotationsSvg.style.opacity = this.showAnnotations ? '1' : '0';
    }

    const txt = document.getElementById('txt-toggle-annotations');
    if (txt) {
      txt.textContent = `Annotations: ${this.showAnnotations ? 'ON' : 'OFF'}`;
    }
  }

  /**
   * Computes the current 3D world position for each anatomical structure
   */
  _getAnchorWorldPos(def, outVec) {
    if (def.jointName && this.joints[def.jointName]) {
      this.joints[def.jointName].getWorldPosition(outVec);
      return outVec;
    }

    // Otherwise use fallback transformed by model matrix if present
    if (this.model) {
      outVec.copy(def.fallbackAnchor);
      outVec.applyMatrix4(this.model.matrixWorld);
      return outVec;
    }

    outVec.copy(def.fallbackAnchor);
    return outVec;
  }

  /**
   * Updates projection coordinates and renders DOM annotations each frame
   */
  _updateAnnotations() {
    if (!this.showAnnotations || !this.camera || !this.canvas || this.annotationElements.length === 0) {
      return;
    }

    const rect = this.canvas.getBoundingClientRect();
    const width = rect.width || this.canvas.clientWidth;
    const height = rect.height || this.canvas.clientHeight;

    if (width === 0 || height === 0) return;

    // Viewport bounds for collision clamping
    const minX = 12;
    const maxX = width - 12;
    const minY = 38; // Below top HUD
    const maxY = height - 42; // Above bottom HUD

    // Update live values from window.__CARDIA_STATE
    const state = window.__CARDIA_STATE;

    this.annotationElements.forEach((item) => {
      const { def, pin, path, card, valEl } = item;

      // 1. Get world coordinate and project to screen space
      this._getAnchorWorldPos(def, this._tempVec);

      // Check if behind camera
      this._tempVec.project(this.camera);
      const isBehindCamera = this._tempVec.z > 1.0;

      if (isBehindCamera) {
        pin.style.display = 'none';
        card.style.display = 'none';
        path.setAttribute('d', '');
        return;
      }

      pin.style.display = 'block';
      card.style.display = 'block';

      // Screen coordinates (in pixels relative to container)
      const screenX = (this._tempVec.x * 0.5 + 0.5) * width;
      const screenY = (-(this._tempVec.y * 0.5) + 0.5) * height;

      // Position anchor pin
      pin.style.left = `${Math.round(screenX)}px`;
      pin.style.top = `${Math.round(screenY)}px`;

      // Depth based opacity (fade slightly when facing away or occluded in Z)
      const depthOpacity = Math.max(0.35, Math.min(1.0, 1.0 - (this._tempVec.z - 0.7) * 1.5));
      pin.style.opacity = `${depthOpacity}`;

      // Card target positioning with screen-side bias
      const cardW = card.offsetWidth || 130;
      const cardH = card.offsetHeight || 38;

      let cardX, cardY;
      if (def.screenSide === 'left') {
        cardX = screenX + def.offset.x - cardW;
        cardY = screenY + def.offset.y;
      } else {
        cardX = screenX + def.offset.x;
        cardY = screenY + def.offset.y;
      }

      // Clamp within safe viewport borders
      cardX = Math.max(minX, Math.min(maxX - cardW, cardX));
      cardY = Math.max(minY, Math.min(maxY - cardH, cardY));

      card.style.left = `${Math.round(cardX)}px`;
      card.style.top = `${Math.round(cardY)}px`;
      card.style.opacity = `${this.activeHoverId === def.id ? 1.0 : Math.max(0.75, depthOpacity)}`;

      // Draw SVG leader path: anchor pin -> elbow -> card edge
      const attachX = def.screenSide === 'left' ? cardX + cardW : cardX;
      const attachY = cardY + cardH * 0.5;

      // Smooth elbow curve
      const midX = (screenX + attachX) * 0.5;
      path.setAttribute('d', `M ${screenX.toFixed(1)} ${screenY.toFixed(1)} Q ${midX.toFixed(1)} ${screenY.toFixed(1)}, ${attachX.toFixed(1)} ${attachY.toFixed(1)}`);

      // Update live telemetry badge
      if (valEl && state) {
        if (def.liveKey && state.live && state.live.chambers && state.live.chambers[def.liveKey]) {
          const ch = state.live.chambers[def.liveKey];
          valEl.textContent = `${Math.round(ch.volume_ml)}mL · ${Math.round(ch.pressure_mmhg)}mmHg`;
        } else if (def.liveValve && state.live && state.live.valves && state.live.valves[def.liveValve]) {
          const v = state.live.valves[def.liveValve];
          valEl.textContent = v.is_open ? 'OPEN' : 'CLOSED';
          valEl.style.color = v.is_open ? '#059669' : '#64748b';
        } else if (def.liveCirc && state.live) {
          if (def.id === 'aorta') {
            valEl.textContent = `${Math.round(state.live.sbp || 120)}/${Math.round(state.live.dbp || 80)} mmHg`;
          } else if (def.id === 'pulmonaryArtery') {
            valEl.textContent = `P: ${Math.round((state.live.dbp || 80) * 0.2)} mmHg`;
          }
        }
      }
    });
  }

  /**
   * Create subtle glow overlays around the heart that respond to
   * contractility and valve states.
   */
  _createGlowOverlays() {
    if (!this.model) return;

    const glowGeo = new THREE.SphereGeometry(0.7, 32, 32);
    const glowMat = new THREE.MeshBasicMaterial({
      color: 0x0284c7,
      transparent: true,
      opacity: 0.0,
      side: THREE.BackSide,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    this._innerGlow = new THREE.Mesh(glowGeo, glowMat);
    this._innerGlow.position.copy(this.model.position);
    this.scene.add(this._innerGlow);
  }

  /**
   * Sync animation playback speed to heart rate.
   */
  _syncAnimationToHR(hr) {
    if (!this.animAction) return;
    const clampedHR = Math.max(20, Math.min(220, hr));
    this.animAction.timeScale = clampedHR / 60.0;
    this.lastHR = clampedHR;
  }

  /**
   * Apply telemetry-driven visual effects each frame.
   */
  _applyTelemetry() {
    const state = window.__CARDIA_STATE;
    if (!state) return;

    // 1. Sync animation speed to live heart rate
    if (Math.abs(state.hr - this.lastHR) > 0.5) {
      this._syncAnimationToHR(state.hr);
    }

    // 2. Pause/resume animation when simulation is paused
    if (this.animAction) {
      if (!state.running && this.animAction.isRunning()) {
        this.animAction.paused = true;
      } else if (state.running && this.animAction.paused) {
        this.animAction.paused = false;
      }
    }

    // 3. Contractility -> inner glow
    if (this._innerGlow) {
      const contractility = state.contractility || 1.0;
      const phase = state.cyclePhase || 0;
      const systolicIntensity = phase < 0.35
        ? Math.sin((phase / 0.35) * Math.PI) * 0.12
        : 0;
      const contractGlow = Math.max(0, (contractility - 0.5) * 0.08);
      this._innerGlow.material.opacity = systolicIntensity + contractGlow;

      if (contractility < 0.7) {
        this._innerGlow.material.color.setHex(0xd97706);
      } else if (contractility > 1.5) {
        this._innerGlow.material.color.setHex(0x059669);
      } else {
        this._innerGlow.material.color.setHex(0x0284c7);
      }
    }

    // 4. Valve state -> tint
    if (this.model && state.live && state.live.valves) {
      const v = state.live.valves;
      const aorticOpen = v.aortic?.is_open ?? false;

      this.model.traverse((child) => {
        if (child.isMesh && child.material && child.material.isMeshStandardMaterial) {
          if (aorticOpen) {
            if (!child.material.emissive) {
              child.material.emissive = new THREE.Color(0x000000);
            }
            child.material.emissive.setHex(0x0284c7);
            child.material.emissiveIntensity = 0.06;
          } else {
            child.material.emissiveIntensity = 0.0;
          }
        }
      });
    }

    // 5. EF alarm
    if (state.live && state.live.ef < 35) {
      const alarm = Math.sin(performance.now() * 0.005) * 0.5 + 0.5;
      this.rimLight.color.setHex(0xdc2626);
      this.rimLight.intensity = 0.3 + alarm * 0.7;
    } else {
      this.rimLight.color.setHex(0xaaccee);
      this.rimLight.intensity = 0.4;
    }
  }

  /**
   * Bind mouse/touch input for orbit controls.
   */
  _bindInputs() {
    if (!this.canvas) return;

    this.canvas.addEventListener('contextmenu', (e) => e.preventDefault());

    this.canvas.addEventListener('mousedown', (e) => {
      this._isDragging = true;
      this._prevX = e.clientX;
      this._prevY = e.clientY;
      this.canvas.style.cursor = 'grabbing';
    });

    window.addEventListener('mouseup', () => {
      this._isDragging = false;
      if (this.canvas) this.canvas.style.cursor = 'grab';
    });

    window.addEventListener('mousemove', (e) => {
      if (!this._isDragging) return;
      const dx = e.clientX - this._prevX;
      const dy = e.clientY - this._prevY;
      this._theta -= dx * 0.008;
      this._phi = Math.max(0.3, Math.min(Math.PI - 0.3, this._phi - dy * 0.008));
      this._prevX = e.clientX;
      this._prevY = e.clientY;
      this._updateCameraFromSpherical();
    });

    this.canvas.addEventListener('wheel', (e) => {
      this._radius = Math.max(1.5, Math.min(8.0, this._radius + e.deltaY * 0.003));
      this._updateCameraFromSpherical();
      e.preventDefault();
    }, { passive: false });

    // Touch support
    let touchStartDist = 0;
    this.canvas.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) {
        this._isDragging = true;
        this._prevX = e.touches[0].clientX;
        this._prevY = e.touches[0].clientY;
      } else if (e.touches.length === 2) {
        touchStartDist = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
      }
    }, { passive: true });

    this.canvas.addEventListener('touchmove', (e) => {
      if (e.touches.length === 1 && this._isDragging) {
        const dx = e.touches[0].clientX - this._prevX;
        const dy = e.touches[0].clientY - this._prevY;
        this._theta -= dx * 0.008;
        this._phi = Math.max(0.3, Math.min(Math.PI - 0.3, this._phi - dy * 0.008));
        this._prevX = e.touches[0].clientX;
        this._prevY = e.touches[0].clientY;
        this._updateCameraFromSpherical();
      } else if (e.touches.length === 2) {
        const dist = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
        const delta = touchStartDist - dist;
        this._radius = Math.max(1.5, Math.min(8.0, this._radius + delta * 0.005));
        touchStartDist = dist;
        this._updateCameraFromSpherical();
      }
      e.preventDefault();
    }, { passive: false });

    this.canvas.addEventListener('touchend', () => {
      this._isDragging = false;
    }, { passive: true });
  }

  /**
   * Convert spherical coordinates to camera position
   */
  _updateCameraFromSpherical() {
    if (!this.camera || !this._target) return;
    const x = this._radius * Math.sin(this._phi) * Math.cos(this._theta);
    const y = this._radius * Math.cos(this._phi);
    const z = this._radius * Math.sin(this._phi) * Math.sin(this._theta);
    this.camera.position.set(
      this._target.x + x,
      this._target.y + y,
      this._target.z + z
    );
    this.camera.lookAt(this._target);
  }

  /**
   * Main animation loop
   */
  _animate() {
    if (this.disposed) return;
    requestAnimationFrame(() => this._animate());

    const delta = this.clock.getDelta();

    // Update animation mixer (drives skeletal animation)
    if (this.mixer) {
      this.mixer.update(delta);
    }

    // Apply simulator telemetry to visuals
    if (this.isLoaded) {
      this._applyTelemetry();
      this._updateAnnotations();
    }

    // Resize check
    this._handleResize();

    // Render
    if (this.renderer && this.scene && this.camera) {
      this.renderer.render(this.scene, this.camera);
    }
  }

  /**
   * Handle canvas resize
   */
  _handleResize() {
    if (!this.canvas || !this.renderer || !this.camera) return;
    const rect = this.canvas.getBoundingClientRect();
    const w = Math.floor(rect.width);
    const h = Math.floor(rect.height);

    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.renderer.setSize(w, h, false);
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
    }
  }

  /**
   * Clean up all resources
   */
  dispose() {
    this.disposed = true;
    if (this.mixer) this.mixer.stopAllAction();
    if (this.renderer) {
      this.renderer.dispose();
      this.renderer.forceContextLoss();
    }
    if (this.annotationsContainer && this.annotationsContainer.parentElement) {
      this.annotationsContainer.parentElement.removeChild(this.annotationsContainer);
    }
    if (this.annotationsSvg && this.annotationsSvg.parentElement) {
      this.annotationsSvg.parentElement.removeChild(this.annotationsSvg);
    }
    const toggleBtn = document.getElementById('btn-toggle-annotations');
    if (toggleBtn && toggleBtn.parentElement) {
      toggleBtn.parentElement.removeChild(toggleBtn);
    }
    if (this.scene) {
      this.scene.traverse((obj) => {
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) {
          if (Array.isArray(obj.material)) {
            obj.material.forEach(m => m.dispose());
          } else {
            obj.material.dispose();
          }
        }
      });
    }
    console.log('[CardiaHeart3D] Disposed.');
  }
}

// Expose globally for integration
window.CardiaHeart3D = CardiaHeart3D;
