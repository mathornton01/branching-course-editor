/**
 * silva-common.js — site-wide shared module for Silva Paideia / CourseForge.
 *
 * Provides:
 *   - window.Silva.auth   — unified auth state + login/register/logout (all pages)
 *   - window.Silva.radio  — persistent ambient radio that auto-resumes across pages
 *   - window.Silva.toast  — lightweight toast notifications
 *   - window.Silva.injectNavWidget()     — drop a sign-in / user-chip into any nav
 *   - window.Silva.installRadioWidget()  — drop the floating radio control
 *   - window.Silva.installGlobalKeys()   — keyboard shortcuts (? help, / search, g h home, g s store…)
 *
 * This file is linked from every public page so the whole site shares one
 * source of truth for auth, ambient audio, navigation, and QoL behaviour.
 *
 * Usage (any page):
 *   <script src="/silva-common.js" defer></script>
 *   <script>
 *     window.addEventListener('DOMContentLoaded', () => {
 *       Silva.injectNavWidget('#nav-right');
 *       Silva.installRadioWidget();
 *       Silva.installGlobalKeys();
 *     });
 *   </script>
 */

(function () {
  'use strict';

  const API = '';
  const LS = {
    token: 'auth_token',
    user: 'auth_user',
    radioOn: 'silva_radio_on',
    radioVolume: 'silva_radio_volume',
    radioStation: 'silva_radio_station',
    radioMuted: 'silva_radio_muted',
  };

  // ────────────────────────────────────────────────────────────────────
  // AUTH
  // ────────────────────────────────────────────────────────────────────
  const Auth = {
    get token() { return localStorage.getItem(LS.token); },
    get user() {
      try { return JSON.parse(localStorage.getItem(LS.user) || 'null'); }
      catch (e) { return null; }
    },
    get isAuthenticated() { return !!this.token && !!this.user; },
    get isInstructor() {
      const u = this.user;
      return !!u && (u.role === 'instructor' || u.role === 'professor' || u.role === 'admin');
    },
    get isStudent() {
      const u = this.user;
      return !!u && u.role === 'student';
    },

    set(token, user) {
      localStorage.setItem(LS.token, token);
      localStorage.setItem(LS.user, JSON.stringify(user));
      window.dispatchEvent(new CustomEvent('silva:auth-changed', { detail: { user, token } }));
    },

    clear() {
      localStorage.removeItem(LS.token);
      localStorage.removeItem(LS.user);
      window.dispatchEvent(new CustomEvent('silva:auth-changed', { detail: { user: null, token: null } }));
    },

    async login(identifier, password) {
      const res = await fetch(API + '/api/auth?action=login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: identifier, email: identifier, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || data.detail || 'Login failed');
      this.set(data.token, data.user);
      return data.user;
    },

    async register({ email, username, password, role, display_name }) {
      const res = await fetch(API + '/api/auth?action=register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, username, password, role, display_name }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || data.detail || 'Registration failed');
      this.set(data.token, data.user);
      return data.user;
    },

    async validate() {
      const t = this.token;
      if (!t) return null;
      try {
        const res = await fetch(API + '/api/auth?action=validate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token: t }),
        });
        if (!res.ok) { this.clear(); return null; }
        const data = await res.json();
        if (data.valid && data.user) {
          localStorage.setItem(LS.user, JSON.stringify(data.user));
          return data.user;
        }
        this.clear();
        return null;
      } catch (e) {
        // Network error — keep existing state, try again later.
        return this.user;
      }
    },

    logout(redirect) {
      this.clear();
      if (redirect !== false) {
        setTimeout(() => { window.location.href = '/login.html'; }, 300);
      }
    },

    authHeader() {
      const t = this.token;
      return t ? { Authorization: 'Bearer ' + t } : {};
    },
  };

  // ────────────────────────────────────────────────────────────────────
  // AMBIENT RADIO
  //   Auto-resumes across page navigations if it was playing.
  //   Browsers block autoplay until user gesture — we store an intent flag
  //   and, on any page load, try to play; if blocked, the widget shows
  //   "Click to resume" so the user's next click restores sound.
  // ────────────────────────────────────────────────────────────────────
  const STATIONS = [
    { id: 'drone',   name: 'Drone Zone',  url: 'https://ice1.somafm.com/dronezone-128-mp3',  hint: 'Ambient atmospheres' },
    { id: 'deep',    name: 'Deep Space',  url: 'https://ice1.somafm.com/deepspaceone-128-mp3', hint: 'Spacey, slow' },
    { id: 'groove',  name: 'Groove Salad',url: 'https://ice1.somafm.com/groovesalad-128-mp3', hint: 'Chill beats' },
    { id: 'fluid',   name: 'Fluid',       url: 'https://ice1.somafm.com/fluid-128-mp3',        hint: 'Liquid DnB / chill' },
    { id: 'forest',  name: 'Forest (birds)', url: 'https://cdn.freesound.org/previews/531/531015_10779090-lq.mp3', hint: 'Birds & leaves', loop: true },
  ];

  const Radio = {
    audio: null,
    _stationId: null,
    _started: false,
    _blockedByAutoplay: false,
    _onStateChange: new Set(),

    _boot() {
      if (this.audio) return;
      const a = new Audio();
      a.crossOrigin = 'anonymous';
      a.preload = 'none';
      a.volume = this._initialVolume();
      this.audio = a;
      a.addEventListener('playing', () => { this._blockedByAutoplay = false; this._emit(); });
      a.addEventListener('pause',   () => this._emit());
      a.addEventListener('error',   () => this._emit());
      // Persistent across pages via localStorage + auto-resume
      this._stationId = localStorage.getItem(LS.radioStation) || STATIONS[0].id;
      this._applyStation(this._stationId, { keepWanted: true });
    },

    _initialVolume() {
      const v = parseFloat(localStorage.getItem(LS.radioVolume));
      if (isFinite(v) && v >= 0 && v <= 1) return v;
      return 0.10; // default: very quiet
    },

    get stations() { return STATIONS.slice(); },
    get station() { return STATIONS.find(s => s.id === this._stationId) || STATIONS[0]; },
    get volume()  { return this.audio ? this.audio.volume : this._initialVolume(); },
    get muted()   { return localStorage.getItem(LS.radioMuted) === '1'; },
    get playing() { return this.audio && !this.audio.paused; },
    get wanted()  { return localStorage.getItem(LS.radioOn) === '1'; }, // user intent
    get blocked() { return this._blockedByAutoplay; },

    setVolume(v) {
      v = Math.max(0, Math.min(1, v));
      localStorage.setItem(LS.radioVolume, v.toFixed(3));
      if (this.audio) this.audio.volume = this.muted ? 0 : v;
      this._emit();
    },

    setMuted(m) {
      localStorage.setItem(LS.radioMuted, m ? '1' : '0');
      if (this.audio) this.audio.volume = m ? 0 : this._initialVolume();
      this._emit();
    },

    _applyStation(id, { keepWanted = false } = {}) {
      const st = STATIONS.find(s => s.id === id) || STATIONS[0];
      this._stationId = st.id;
      localStorage.setItem(LS.radioStation, st.id);
      if (!this.audio) return;
      const wasPlaying = this.wanted || this.playing;
      this.audio.src = st.url;
      this.audio.loop = !!st.loop;
      if (wasPlaying || keepWanted && this.wanted) {
        this._tryPlay();
      }
      this._emit();
    },

    setStation(id) { this._applyStation(id); },

    async _tryPlay() {
      this._boot();
      try {
        this.audio.volume = this.muted ? 0 : this._initialVolume();
        await this.audio.play();
        this._blockedByAutoplay = false;
      } catch (e) {
        this._blockedByAutoplay = true;
      }
      this._emit();
    },

    async play() {
      localStorage.setItem(LS.radioOn, '1');
      await this._tryPlay();
    },

    pause() {
      localStorage.setItem(LS.radioOn, '0');
      if (this.audio) this.audio.pause();
      this._emit();
    },

    toggle() { this.playing ? this.pause() : this.play(); },

    onChange(fn) { this._onStateChange.add(fn); return () => this._onStateChange.delete(fn); },
    _emit() { this._onStateChange.forEach(fn => { try { fn(); } catch (e) {} }); },

    // Called once on page load. If the user's last action said "on", we try
    // to resume. If the browser blocks it, we install a one-shot gesture
    // listener so the next click/keypress silently kicks playback back on.
    autoResume() {
      this._boot();
      if (!this.wanted) return;
      this._tryPlay().then(() => {
        if (this._blockedByAutoplay) {
          const kick = () => {
            this._tryPlay();
            document.removeEventListener('click', kick, true);
            document.removeEventListener('keydown', kick, true);
            document.removeEventListener('touchstart', kick, true);
          };
          document.addEventListener('click',      kick, true);
          document.addEventListener('keydown',    kick, true);
          document.addEventListener('touchstart', kick, true);
        }
      });
    },
  };

  // ────────────────────────────────────────────────────────────────────
  // TOAST
  // ────────────────────────────────────────────────────────────────────
  function ensureToastRoot() {
    let r = document.getElementById('silva-toast-root');
    if (r) return r;
    r = document.createElement('div');
    r.id = 'silva-toast-root';
    r.style.cssText = 'position:fixed;bottom:22px;left:50%;transform:translateX(-50%);z-index:9999;display:flex;flex-direction:column;gap:8px;align-items:center;pointer-events:none;';
    document.body.appendChild(r);
    return r;
  }

  const Toast = {
    show(msg, type = 'info', ms = 2800) {
      const r = ensureToastRoot();
      const colors = {
        info:    { bg: '#142e19', bd: '#3daa5c', fg: '#d8e8d0' },
        success: { bg: '#0e2a18', bd: '#34d399', fg: '#b5f0cc' },
        error:   { bg: '#2a1414', bd: '#e8735a', fg: '#ffcec4' },
        warn:    { bg: '#2a230e', bd: '#d4a843', fg: '#ffe7a8' },
      };
      const c = colors[type] || colors.info;
      const el = document.createElement('div');
      el.textContent = msg;
      el.style.cssText = `pointer-events:auto;background:${c.bg};border:1px solid ${c.bd};color:${c.fg};padding:10px 18px;border-radius:10px;font-size:14px;box-shadow:0 4px 20px rgba(0,0,0,0.35);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;opacity:0;transform:translateY(6px);transition:opacity .18s,transform .18s;max-width:420px;`;
      r.appendChild(el);
      requestAnimationFrame(() => { el.style.opacity = '1'; el.style.transform = 'translateY(0)'; });
      setTimeout(() => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(6px)';
        setTimeout(() => el.remove(), 200);
      }, ms);
    },
    success(m, ms) { this.show(m, 'success', ms); },
    error(m, ms)   { this.show(m, 'error', ms); },
    warn(m, ms)    { this.show(m, 'warn', ms); },
  };

  // ────────────────────────────────────────────────────────────────────
  // SIGN-IN MODAL (drop-in for any page without its own modal)
  // ────────────────────────────────────────────────────────────────────
  let _modalEl = null;
  function ensureSignInModal() {
    if (_modalEl) return _modalEl;
    const el = document.createElement('div');
    el.id = 'silva-signin-modal';
    el.style.cssText = 'position:fixed;inset:0;background:rgba(5,12,8,0.75);display:none;align-items:center;justify-content:center;z-index:9998;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;';
    el.innerHTML = `
      <div style="background:#0f2213;border:1px solid #1e4a26;border-radius:14px;padding:28px;max-width:420px;width:calc(100% - 32px);color:#d8e8d0;box-shadow:0 20px 60px rgba(0,0,0,0.6);">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;">
          <h3 id="sv-modal-title" style="font-size:18px;margin:0;">Sign in</h3>
          <button id="sv-modal-close" aria-label="Close" style="background:none;border:none;color:#7ea57a;font-size:22px;cursor:pointer;line-height:1;">×</button>
        </div>
        <div id="sv-modal-tabs" style="display:flex;gap:4px;background:#142e19;border:1px solid #1e4a26;border-radius:10px;padding:4px;margin-bottom:18px;">
          <button data-tab="login"    class="sv-tab-btn">Sign in</button>
          <button data-tab="register" class="sv-tab-btn">Create account</button>
        </div>
        <div id="sv-reg-only" style="display:none;">
          <label style="display:block;font-size:12px;color:#7ea57a;margin-bottom:4px;">Display name</label>
          <input id="sv-display" type="text" placeholder="Your name" style="width:100%;margin-bottom:10px;" />
          <label style="display:block;font-size:12px;color:#7ea57a;margin-bottom:4px;">Username</label>
          <input id="sv-username" type="text" placeholder="username" style="width:100%;margin-bottom:10px;" />
          <label style="display:block;font-size:12px;color:#7ea57a;margin-bottom:4px;">I am a…</label>
          <select id="sv-role" style="width:100%;margin-bottom:10px;">
            <option value="student">Student — enroll &amp; learn</option>
            <option value="instructor">Professor — author courses</option>
          </select>
        </div>
        <label style="display:block;font-size:12px;color:#7ea57a;margin-bottom:4px;">Email or username</label>
        <input id="sv-id" type="text" placeholder="you@example.com" style="width:100%;margin-bottom:10px;" />
        <label style="display:block;font-size:12px;color:#7ea57a;margin-bottom:4px;">Password</label>
        <input id="sv-pw" type="password" placeholder="Password" style="width:100%;margin-bottom:14px;" />
        <div id="sv-err" style="display:none;color:#e8735a;font-size:13px;margin-bottom:10px;"></div>
        <button id="sv-submit" style="width:100%;padding:11px;border-radius:8px;border:none;background:#3daa5c;color:#fff;font-size:14px;font-weight:600;cursor:pointer;">Sign in</button>
        <div style="text-align:center;margin-top:14px;font-size:13px;">
          <a id="sv-fullpage" href="/login.html" style="color:#5ec97b;text-decoration:none;">More options on the full sign-in page →</a>
        </div>
      </div>`;
    document.body.appendChild(el);
    // inputs default style
    el.querySelectorAll('input,select').forEach(i => {
      i.style.cssText += 'background:#142e19;border:1px solid #1e4a26;border-radius:8px;padding:10px 12px;color:#d8e8d0;font-size:14px;outline:none;font-family:inherit;';
    });
    el.querySelectorAll('.sv-tab-btn').forEach(b => {
      b.style.cssText = 'flex:1;padding:8px;background:none;border:none;color:#7ea57a;font-size:13px;cursor:pointer;border-radius:7px;font-weight:600;';
    });

    const setTab = (tab) => {
      el.querySelectorAll('.sv-tab-btn').forEach(b => {
        const active = b.dataset.tab === tab;
        b.style.background = active ? '#1c3d22' : 'transparent';
        b.style.color = active ? '#d8e8d0' : '#7ea57a';
      });
      el.querySelector('#sv-reg-only').style.display = tab === 'register' ? 'block' : 'none';
      el.querySelector('#sv-modal-title').textContent = tab === 'register' ? 'Create account' : 'Sign in';
      el.querySelector('#sv-submit').textContent = tab === 'register' ? 'Create account' : 'Sign in';
      el._tab = tab;
    };
    setTab('login');

    el.querySelectorAll('.sv-tab-btn').forEach(b => {
      b.addEventListener('click', () => setTab(b.dataset.tab));
    });
    el.querySelector('#sv-modal-close').addEventListener('click', () => closeSignInModal());
    el.addEventListener('click', (e) => { if (e.target === el) closeSignInModal(); });

    const submit = async () => {
      const err = el.querySelector('#sv-err');
      err.style.display = 'none';
      const btn = el.querySelector('#sv-submit');
      btn.disabled = true;
      const origText = btn.textContent;
      btn.textContent = el._tab === 'register' ? 'Creating…' : 'Signing in…';
      try {
        const id = el.querySelector('#sv-id').value.trim();
        const pw = el.querySelector('#sv-pw').value;
        if (!id || !pw) throw new Error('Email/username and password are required.');
        if (el._tab === 'register') {
          const username = el.querySelector('#sv-username').value.trim();
          const display = el.querySelector('#sv-display').value.trim();
          const role = el.querySelector('#sv-role').value;
          if (!username) throw new Error('Pick a username.');
          await Auth.register({ email: id, username, password: pw, role, display_name: display || username });
          Toast.success('Welcome, ' + (display || username) + '!');
        } else {
          const u = await Auth.login(id, pw);
          Toast.success('Welcome back, ' + (u.display_name || u.username) + '!');
        }
        closeSignInModal();
        // Re-render nav widget
        document.querySelectorAll('[data-silva-nav-target]').forEach(n => {
          window.Silva.injectNavWidget(n);
        });
      } catch (e) {
        err.textContent = e.message || String(e);
        err.style.display = 'block';
      } finally {
        btn.disabled = false;
        btn.textContent = origText;
      }
    };
    el.querySelector('#sv-submit').addEventListener('click', submit);
    el.querySelectorAll('input').forEach(i => i.addEventListener('keydown', e => {
      if (e.key === 'Enter') submit();
    }));
    _modalEl = el;
    return el;
  }

  function openSignInModal(tab = 'login') {
    const el = ensureSignInModal();
    el.style.display = 'flex';
    el.querySelectorAll('.sv-tab-btn').forEach(b => {
      if (b.dataset.tab === tab) b.click();
    });
    setTimeout(() => el.querySelector('#sv-id').focus(), 50);
  }
  function closeSignInModal() {
    if (_modalEl) _modalEl.style.display = 'none';
  }

  // ────────────────────────────────────────────────────────────────────
  // NAV WIDGET
  //   Any page can call:  Silva.injectNavWidget('#nav-right')
  //   Creates/updates a chip or sign-in buttons in the given container.
  // ────────────────────────────────────────────────────────────────────
  function injectNavWidget(target) {
    const el = typeof target === 'string' ? document.querySelector(target) : target;
    if (!el) return;
    el.setAttribute('data-silva-nav-target', '1');
    if (Auth.isAuthenticated) {
      const u = Auth.user;
      const initial = ((u.display_name || u.username || '?')[0] || '?').toUpperCase();
      const role = Auth.isInstructor ? 'Professor' : 'Student';
      el.innerHTML = `
        <div class="silva-user-chip" style="display:flex;align-items:center;gap:8px;background:#142e19;border:1px solid #1e4a26;border-radius:20px;padding:4px 4px 4px 4px;font-size:13px;color:#d8e8d0;cursor:pointer;position:relative;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
          <div style="width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,#3daa5c,#d4a843);display:flex;align-items:center;justify-content:center;font-weight:700;color:#fff;font-size:13px;">${initial}</div>
          <span style="padding:0 4px;">${escapeHtml(u.display_name || u.username)}</span>
          <span style="font-size:10px;padding:2px 8px;border-radius:10px;font-weight:600;background:rgba(52,211,153,0.15);color:#34d399;margin-right:6px;">${role}</span>
          <div class="silva-user-menu" style="position:absolute;top:calc(100% + 6px);right:0;background:#0f2213;border:1px solid #1e4a26;border-radius:10px;padding:6px;min-width:200px;display:none;z-index:500;box-shadow:0 8px 24px rgba(0,0,0,0.5);">
            <a href="/" style="display:block;padding:8px 12px;color:#d8e8d0;font-size:13px;border-radius:6px;text-decoration:none;">Home</a>
            <a href="/store.html" style="display:block;padding:8px 12px;color:#d8e8d0;font-size:13px;border-radius:6px;text-decoration:none;">Course Store</a>
            <a href="/player.html" style="display:block;padding:8px 12px;color:#d8e8d0;font-size:13px;border-radius:6px;text-decoration:none;">Course Player</a>
            ${Auth.isInstructor ? `
              <a href="/course-editor-enhanced.html" style="display:block;padding:8px 12px;color:#d8e8d0;font-size:13px;border-radius:6px;text-decoration:none;">Editor</a>
              <a href="/instructor-dashboard.html" style="display:block;padding:8px 12px;color:#d8e8d0;font-size:13px;border-radius:6px;text-decoration:none;">Dashboard</a>
            ` : ''}
            <div style="height:1px;background:#1e4a26;margin:6px 0;"></div>
            <a href="#" data-silva-logout style="display:block;padding:8px 12px;color:#e8735a;font-size:13px;border-radius:6px;text-decoration:none;">Sign out</a>
          </div>
        </div>`;
      const chip = el.querySelector('.silva-user-chip');
      const menu = el.querySelector('.silva-user-menu');
      chip.addEventListener('click', (e) => {
        e.stopPropagation();
        menu.style.display = menu.style.display === 'block' ? 'none' : 'block';
      });
      document.addEventListener('click', () => { menu.style.display = 'none'; });
      menu.querySelectorAll('a').forEach(a => a.addEventListener('click', (e) => {
        if (a.hasAttribute('data-silva-logout')) {
          e.preventDefault();
          Auth.logout();
        }
      }));
    } else {
      el.innerHTML = `
        <button data-silva-signin="login" class="silva-signin-btn" style="padding:8px 16px;border-radius:8px;border:1px solid #1e4a26;background:#142e19;color:#d8e8d0;font-size:13px;cursor:pointer;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">Sign in</button>
        <button data-silva-signin="register" style="padding:8px 16px;border-radius:8px;border:none;background:#3daa5c;color:#fff;font-size:13px;font-weight:600;cursor:pointer;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">Get started</button>`;
      el.querySelectorAll('[data-silva-signin]').forEach(b => {
        b.addEventListener('click', () => openSignInModal(b.getAttribute('data-silva-signin')));
      });
    }
  }

  // Auto-update any nav widgets when auth changes.
  window.addEventListener('silva:auth-changed', () => {
    document.querySelectorAll('[data-silva-nav-target]').forEach(el => injectNavWidget(el));
  });

  // ────────────────────────────────────────────────────────────────────
  // RADIO WIDGET — floating bottom-right
  // ────────────────────────────────────────────────────────────────────
  function installRadioWidget() {
    if (document.getElementById('silva-radio-widget')) return;
    const w = document.createElement('div');
    w.id = 'silva-radio-widget';
    w.style.cssText = 'position:fixed;right:16px;bottom:16px;background:rgba(15,34,19,0.92);backdrop-filter:blur(8px);border:1px solid #1e4a26;border-radius:14px;padding:8px 10px;display:flex;align-items:center;gap:8px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:12px;color:#d8e8d0;z-index:900;box-shadow:0 6px 18px rgba(0,0,0,0.4);user-select:none;max-width:calc(100% - 32px);';
    w.innerHTML = `
      <button id="sv-radio-toggle" title="Play ambient radio" style="width:34px;height:34px;border-radius:50%;border:none;background:#3daa5c;color:#fff;font-size:14px;cursor:pointer;display:flex;align-items:center;justify-content:center;">▶</button>
      <div style="display:flex;flex-direction:column;line-height:1.2;min-width:0;">
        <span id="sv-radio-title" style="font-size:12px;font-weight:600;color:#d8e8d0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:130px;">Ambient radio</span>
        <span id="sv-radio-sub" style="font-size:10px;color:#7ea57a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:130px;">Off</span>
      </div>
      <input id="sv-radio-vol" type="range" min="0" max="100" value="10" title="Volume" style="width:70px;accent-color:#3daa5c;" />
      <button id="sv-radio-station" title="Change station" style="background:none;border:1px solid #1e4a26;border-radius:6px;color:#7ea57a;padding:3px 6px;cursor:pointer;font-size:11px;">⇄</button>
      <button id="sv-radio-close" title="Hide" style="background:none;border:none;color:#5a7a5a;font-size:14px;cursor:pointer;padding:0 2px;">×</button>
    `;
    document.body.appendChild(w);

    const btn = w.querySelector('#sv-radio-toggle');
    const vol = w.querySelector('#sv-radio-vol');
    const title = w.querySelector('#sv-radio-title');
    const sub = w.querySelector('#sv-radio-sub');
    const stBtn = w.querySelector('#sv-radio-station');
    const closeBtn = w.querySelector('#sv-radio-close');

    const refresh = () => {
      Radio._boot();
      title.textContent = Radio.station.name;
      if (Radio.playing) {
        btn.textContent = '■';
        btn.style.background = '#d4a843';
        btn.title = 'Pause';
        sub.textContent = 'On air · ' + Radio.station.hint;
      } else if (Radio.blocked && Radio.wanted) {
        btn.textContent = '▶';
        btn.style.background = '#e8735a';
        btn.title = 'Click to resume (autoplay was blocked)';
        sub.textContent = 'Click to resume';
      } else {
        btn.textContent = '▶';
        btn.style.background = '#3daa5c';
        btn.title = 'Play';
        sub.textContent = Radio.station.hint;
      }
      const pct = Math.round(Radio.volume * 100);
      if (+vol.value !== pct) vol.value = pct;
    };
    Radio.onChange(refresh);

    btn.addEventListener('click', () => { Radio.toggle(); refresh(); });
    vol.addEventListener('input', () => Radio.setVolume(+vol.value / 100));
    stBtn.addEventListener('click', () => {
      // Cycle through stations.
      const list = Radio.stations;
      const i = list.findIndex(s => s.id === Radio.station.id);
      const next = list[(i + 1) % list.length];
      Radio.setStation(next.id);
      Toast.show('Radio: ' + next.name, 'info', 1400);
      refresh();
    });
    closeBtn.addEventListener('click', () => {
      w.style.display = 'none';
      sessionStorage.setItem('silva_radio_widget_hidden', '1');
    });

    if (sessionStorage.getItem('silva_radio_widget_hidden') === '1') {
      w.style.display = 'none';
    }
    refresh();
  }

  // ────────────────────────────────────────────────────────────────────
  // KEYBOARD SHORTCUTS
  //   g h → home, g s → store, g p → player, g e → editor, g d → dashboard
  //   /   → focus nearest search box
  //   ?   → show help overlay
  //   m   → mute/unmute radio
  //   space → play/pause radio (only if not in input)
  // ────────────────────────────────────────────────────────────────────
  function installGlobalKeys() {
    if (window._silvaKeysInstalled) return;
    window._silvaKeysInstalled = true;

    let gPressed = false;
    let gTimer = 0;
    const inTextInput = () => {
      const a = document.activeElement;
      if (!a) return false;
      const t = (a.tagName || '').toLowerCase();
      return t === 'input' || t === 'textarea' || a.isContentEditable;
    };

    document.addEventListener('keydown', (e) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (inTextInput()) return;

      if (gPressed) {
        gPressed = false;
        clearTimeout(gTimer);
        const map = {
          h: '/',
          s: '/store.html',
          p: '/player.html',
          e: '/course-editor-enhanced.html',
          d: '/instructor-dashboard.html',
          b: '/course-database.html',
          t: '/tutorial.html',
          m: '/manual.html',
        };
        if (map[e.key]) { e.preventDefault(); window.location.href = map[e.key]; }
        return;
      }

      if (e.key === 'g') {
        gPressed = true;
        gTimer = setTimeout(() => { gPressed = false; }, 800);
        return;
      }

      if (e.key === '/') {
        const search = document.querySelector('input[type="search"], #searchInput, input[placeholder*="earch" i]');
        if (search) { e.preventDefault(); search.focus(); }
      } else if (e.key === '?') {
        e.preventDefault();
        showHelpOverlay();
      } else if (e.key === 'm' || e.key === 'M') {
        Radio.setMuted(!Radio.muted);
        Toast.show('Radio ' + (Radio.muted ? 'muted' : 'unmuted'), 'info', 1200);
      } else if (e.key === ' ') {
        // Space toggles radio play/pause, but only if no button is focused.
        if (!document.activeElement || document.activeElement === document.body) {
          e.preventDefault();
          Radio.toggle();
        }
      } else if (e.key === 'Escape') {
        closeSignInModal();
        const help = document.getElementById('silva-help-overlay');
        if (help) help.style.display = 'none';
      }
    });
  }

  function showHelpOverlay() {
    let h = document.getElementById('silva-help-overlay');
    if (h) { h.style.display = 'flex'; return; }
    h = document.createElement('div');
    h.id = 'silva-help-overlay';
    h.style.cssText = 'position:fixed;inset:0;background:rgba(5,12,8,0.78);display:flex;align-items:center;justify-content:center;z-index:9997;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;';
    h.innerHTML = `
      <div style="background:#0f2213;border:1px solid #1e4a26;border-radius:14px;padding:24px;max-width:440px;width:calc(100% - 32px);color:#d8e8d0;box-shadow:0 20px 60px rgba(0,0,0,0.6);">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
          <h3 style="margin:0;font-size:16px;">Keyboard shortcuts</h3>
          <button style="background:none;border:none;color:#7ea57a;font-size:22px;cursor:pointer;" onclick="document.getElementById('silva-help-overlay').style.display='none'">×</button>
        </div>
        <table style="width:100%;font-size:13px;border-collapse:collapse;">
          <tr><td style="padding:4px 8px;color:#7ea57a;"><code>g h</code></td><td style="padding:4px 8px;">Home</td></tr>
          <tr><td style="padding:4px 8px;color:#7ea57a;"><code>g s</code></td><td style="padding:4px 8px;">Store</td></tr>
          <tr><td style="padding:4px 8px;color:#7ea57a;"><code>g p</code></td><td style="padding:4px 8px;">Player</td></tr>
          <tr><td style="padding:4px 8px;color:#7ea57a;"><code>g e</code></td><td style="padding:4px 8px;">Editor</td></tr>
          <tr><td style="padding:4px 8px;color:#7ea57a;"><code>g d</code></td><td style="padding:4px 8px;">Dashboard</td></tr>
          <tr><td style="padding:4px 8px;color:#7ea57a;"><code>g b</code></td><td style="padding:4px 8px;">Browse all</td></tr>
          <tr><td style="padding:4px 8px;color:#7ea57a;"><code>/</code></td><td style="padding:4px 8px;">Focus search</td></tr>
          <tr><td style="padding:4px 8px;color:#7ea57a;"><code>space</code></td><td style="padding:4px 8px;">Play/pause radio</td></tr>
          <tr><td style="padding:4px 8px;color:#7ea57a;"><code>m</code></td><td style="padding:4px 8px;">Mute radio</td></tr>
          <tr><td style="padding:4px 8px;color:#7ea57a;"><code>?</code></td><td style="padding:4px 8px;">This help</td></tr>
          <tr><td style="padding:4px 8px;color:#7ea57a;"><code>esc</code></td><td style="padding:4px 8px;">Close dialogs</td></tr>
        </table>
      </div>`;
    h.addEventListener('click', (e) => { if (e.target === h) h.style.display = 'none'; });
    document.body.appendChild(h);
  }

  // ────────────────────────────────────────────────────────────────────
  // UTIL
  // ────────────────────────────────────────────────────────────────────
  function escapeHtml(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // Validate token in background on every page load.
  function bootValidate() {
    if (Auth.token) {
      Auth.validate().catch(() => {});
    }
  }

  // ────────────────────────────────────────────────────────────────────
  // PUBLIC API
  // ────────────────────────────────────────────────────────────────────
  window.Silva = {
    auth: Auth,
    radio: Radio,
    toast: Toast,
    Toast,           // alias — makes Silva.Toast.show() work too
    openSignInModal,
    closeSignInModal,
    injectNavWidget,
    installRadioWidget,
    installGlobalKeys,
    showHelpOverlay,
    escapeHtml,
    // Convenience: a fetch that auto-adds the Authorization header.
    async apiFetch(url, options = {}) {
      const h = Object.assign({}, options.headers || {}, Auth.authHeader());
      const res = await fetch(url, Object.assign({}, options, { headers: h }));
      return res;
    },
  };

  // Auto-bootstrap minimal features that don't need a specific target.
  window.addEventListener('DOMContentLoaded', () => {
    bootValidate();
    // Radio + keys install themselves unconditionally; pages can opt out
    // by setting  window.SILVA_NO_RADIO = true  or  window.SILVA_NO_KEYS = true
    // before this script runs.
    if (!window.SILVA_NO_RADIO) {
      installRadioWidget();
      Radio.autoResume();
    }
    if (!window.SILVA_NO_KEYS) {
      installGlobalKeys();
    }
    // Auto-upgrade any nav containers tagged with data-silva-nav-auto
    document.querySelectorAll('[data-silva-nav-auto]').forEach(el => injectNavWidget(el));
  });
})();
