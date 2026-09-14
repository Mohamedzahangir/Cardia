/**
 * CARDIA Heart3D — Three.js GLB Integration Module
 * =================================================
 * Loads the beating heart GLB model and drives its animation
 * from the existing SimulationState telemetry pipeline.
 *
 * The existing `window.__CARDIA_STATE` remains the single source of truth.
 * This module READS from it; it never writes physiological values.
 *
 * Usage (from index.html):
 *   const heart3d = new CardiaHeart3D('canvas-cardiac-3d');
 *   heart3d.init();
 *
 * Dependencies (loaded via CDN in index.html BEFORE this script):
 *   - THREE (r160+ from cdn.jsdelivr.net)
 *   - GLTFLoader (from three/examples/jsm/loaders/)
 *   - OrbitControls (optional, we use manual orbit via existing drag handlers)
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

    // Joint mapping for valve/chamber glow overlays
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
    this._theta = -0.4;   // matches existing viewRotY default
    this._phi = 1.37;     // ~78° (slight overhead), matches viewRotX default (0.2 offset from π/2)
    this._radius = 3.2;
    // Orbit target — created in init() once THREE is confirmed available
    this._target = null;

    // Glow meshes for visual feedback
    this._chamberGlows = {};
    this._valveGlows = {};
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

    // --- Scene ---
    this.scene = new THREE.Scene();
    // No background — transparent over the existing CSS grid/vignette
    this.scene.background = null;

    // Create orbit target now that THREE is available
    this._target = new THREE.Vector3(0, 0.3, 0);

    // --- Camera ---
    const rect = this.canvas.getBoundingClientRect();
    this.camera = new THREE.PerspectiveCamera(
      40, rect.width / rect.height, 0.01, 100
    );
    this._updateCameraFromSpherical();

    // --- Renderer ---
    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      antialias: true,
      alpha: true,          // transparent background
      powerPreference: 'high-performance'
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setSize(rect.width, rect.height, false);
    // r148 API: sRGBEncoding; r152+ uses outputColorSpace
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

    // Subtle hemisphere for medical-grade ambient
    const hemiLight = new THREE.HemisphereLight(0xddeeff, 0x8899aa, 0.3);
    this.scene.add(hemiLight);

    // --- Input handling (overrides existing 2D drag) ---
    this._bindInputs();

    // --- Load GLB ---
    await this._loadGLB();

    // --- Start render loop ---
    this._animate();

    console.log('[CardiaHeart3D] Initialized successfully.');
  }

  /**
   * Load the heart GLB model
   */
  _loadGLB() {
    return new Promise((resolve, reject) => {
      // THREE.GLTFLoader is attached to the THREE global via the legacy loader script
      const LoaderClass = THREE.GLTFLoader || (THREE.Loaders && THREE.Loaders.GLTFLoader);
      if (!LoaderClass) {
        reject(new Error('THREE.GLTFLoader not found. Check CDN script ordering.'));
        return;
      }
      const loader = new LoaderClass();

      loader.load(
        '/static/assets/heart.glb',
        (gltf) => {
          this.model = gltf.scene;

          // Scale and position to fit the viewport
          const box = new THREE.Box3().setFromObject(this.model);
          const size = box.getSize(new THREE.Vector3());
          const center = box.getCenter(new THREE.Vector3());
          const maxDim = Math.max(size.x, size.y, size.z);
          const scaleFactor = 2.0 / maxDim;

          this.model.scale.setScalar(scaleFactor);
          this.model.position.sub(center.multiplyScalar(scaleFactor));
          this.model.position.y += 0.3; // Raise slightly

          // Apply enhanced material properties for a clinical look
          this.model.traverse((child) => {
            if (child.isMesh) {
              child.material = child.material.clone();
              // Give the heart a realistic medical-grade appearance
              if (child.material.isMeshStandardMaterial) {
                child.material.roughness = 0.55;
                child.material.metalness = 0.05;
              }
              child.frustumCulled = false;
            }

            // Map joints by name for later telemetry-driven manipulation
            if (child.isBone || child.name.includes('jnt')) {
              this.joints[child.name] = child;
            }
          });

          this.scene.add(this.model);

          // Setup animation
          if (gltf.animations && gltf.animations.length > 0) {
            this.mixer = new THREE.AnimationMixer(this.model);
            const clip = gltf.animations[0]; // "test" clip, 1.0s duration
            this.animAction = this.mixer.clipAction(clip);
            this.animAction.play();
            // Start at HR=74 -> playback speed = 74/60 ≈ 1.23
            this._syncAnimationToHR(74);
          }

          this.isLoaded = true;

          // Create visual overlays for chamber/valve glow
          this._createGlowOverlays();

          console.log('[CardiaHeart3D] GLB loaded. Joints:', Object.keys(this.joints));
          resolve();
        },
        (progress) => {
          const pct = progress.total > 0
            ? Math.round((progress.loaded / progress.total) * 100)
            : '??';
          console.log(`[CardiaHeart3D] Loading GLB... ${pct}%`);
        },
        (error) => {
          console.error('[CardiaHeart3D] GLB load error:', error);
          reject(error);
        }
      );
    });
  }

  /**
   * Create subtle glow overlays around the heart that respond to
   * contractility and valve states.
   */
  _createGlowOverlays() {
    if (!this.model) return;

    // Pulsing inner glow sphere (contractility indicator)
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
   * The GLB animation "test" has 1.0s duration = 60 BPM.
   * For any HR: timeScale = HR / 60
   */
  _syncAnimationToHR(hr) {
    if (!this.animAction) return;
    const clampedHR = Math.max(20, Math.min(220, hr));
    this.animAction.timeScale = clampedHR / 60.0;
    this.lastHR = clampedHR;
  }

  /**
   * Apply telemetry-driven visual effects each frame.
   * Reads from window.__CARDIA_STATE (never writes).
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

    // 3. Contractility → subtle inner glow intensity
    if (this._innerGlow) {
      const contractility = state.contractility || 1.0;
      const phase = state.cyclePhase || 0;
      // Systolic phase = 0..0.35, pulse glow during ejection
      const systolicIntensity = phase < 0.35
        ? Math.sin((phase / 0.35) * Math.PI) * 0.12
        : 0;
      const contractGlow = Math.max(0, (contractility - 0.5) * 0.08);
      this._innerGlow.material.opacity = systolicIntensity + contractGlow;

      // Color shifts: normal=cyan, high contractility=bright blue, low=warm
      if (contractility < 0.7) {
        this._innerGlow.material.color.setHex(0xd97706); // amber warning
      } else if (contractility > 1.5) {
        this._innerGlow.material.color.setHex(0x059669); // emerald hyper
      } else {
        this._innerGlow.material.color.setHex(0x0284c7); // clinical cyan
      }
    }

    // 4. Valve state → tint on the heart material (subtle color feedback)
    if (this.model && state.live && state.live.valves) {
      // We can modulate the model's base color slightly during valve events
      // This provides visual feedback without modifying individual joints
      const v = state.live.valves;
      const aorticOpen = v.aortic?.is_open ?? false;

      // During aortic ejection, add a very subtle brightness boost
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

    // 5. EF-based visual alarm: if EF is critically low, pulse the rim light red
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
   * Overrides the existing 2D canvas drag system for the 3D view.
   */
  _bindInputs() {
    if (!this.canvas) return;

    // Prevent default context menu
    this.canvas.addEventListener('contextmenu', (e) => e.preventDefault());

    // Mouse drag for orbit
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

    // Scroll for zoom
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
    if (!this.camera) return;
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
