/**
 * Uber Driver Intelligence Portal - Application Logic
 * Integrates FastAPI recommendation endpoints with Leaflet map visualization
 */

// Global Application State
const state = {
  driver: null,
  currentZone: 'Z06',
  zonesCatalog: [],          // [{zone_id, zone_name, latitude, longitude}]
  zonesCoordsMap: {},        // 'Z01': {lat, lon, name}
  cityRecommendations: null, // latest run from /recommendations/latest
  personalRecommendations: null, // from /api/recommendations/for-me
  activeDispatch: null,      // {destination_zone_id, zone_name, eta_min, distance_km}
  dispatchInterval: null,

  // Map state
  map: null,
  osmLayer: null,
  trafficOverlay: null,
  isTrafficView: true,
  driverMarker: null,
  zoneMarkers: {},           // 'Z01': L.marker / L.circleMarker
  routePolyline: null,
  routePulseMarker: null,
  chatHistory: [],
  earningsAnalysis: null,
  currentTab: 'personal',
  ttsEnabled: localStorage.getItem('sherpa_tts_enabled') !== 'false',
  isRecordingVoice: false,
  recognition: null,
};

// DOM Elements
const authView = document.getElementById('auth-view');
const dashboardView = document.getElementById('dashboard-view');
const loginForm = document.getElementById('login-form');
const usernameInput = document.getElementById('username');
const passwordInput = document.getElementById('password');
const togglePasswordBtn = document.getElementById('toggle-password-btn');
const loginSubmitBtn = document.getElementById('login-submit-btn');
const loginError = document.getElementById('login-error');
const logoutBtn = document.getElementById('logout-btn');

// Header
const currentZoneSelect = document.getElementById('current-zone-select');
const currentZoneBadge = document.getElementById('current-zone-badge');
const userNameDisplay = document.getElementById('user-name');
const userAvatarDisplay = document.getElementById('user-avatar');
const userRatingDisplay = document.getElementById('user-rating');
const userCarDisplay = document.getElementById('user-car');
const modelRefreshLabel = document.getElementById('model-refresh-label');

// Tabs
const tabPersonalBtn = document.getElementById('tab-personal-btn');
const tabOverallBtn = document.getElementById('tab-overall-btn');
const tabCopilotBtn = document.getElementById('tab-copilot-btn');
const tabAnalyticsBtn = document.getElementById('tab-analytics-btn');
const headerCopilotBtn = document.getElementById('header-copilot-btn');
const headerAnalyticsBtn = document.getElementById('header-analytics-btn');
const panelPersonal = document.getElementById('panel-personal');
const panelOverall = document.getElementById('panel-overall');
const panelCopilot = document.getElementById('panel-copilot');
const panelAnalytics = document.getElementById('panel-analytics');
const personalBadgeCount = document.getElementById('personal-badge-count');
const personalCardsList = document.getElementById('personal-cards-list');
const refreshPersonalBtn = document.getElementById('refresh-personal-btn');

// Analytics DOM Elements
const analyticsMonthlyGain = document.getElementById('analytics-monthly-gain');
const analyticsShiftWith = document.getElementById('analytics-shift-with');
const analyticsShiftWithout = document.getElementById('analytics-shift-without');
const analyticsDriverSelect = document.getElementById('analytics-driver-select');
const driverPersonalizedCallout = document.getElementById('driver-personalized-callout');
const compEarningsPct = document.getElementById('comp-earnings-pct');
const compBaseEarn = document.getElementById('comp-base-earn');
const compModelEarn = document.getElementById('comp-model-earn');
const compEarnDiff = document.getElementById('comp-earn-diff');
const compTripsPct = document.getElementById('comp-trips-pct');
const compBaseTrips = document.getElementById('comp-base-trips');
const compModelTrips = document.getElementById('comp-model-trips');
const compTripsDiff = document.getElementById('comp-trips-diff');
const compWaitPct = document.getElementById('comp-wait-pct');
const compBaseWait = document.getElementById('comp-base-wait');
const compModelWait = document.getElementById('comp-model-wait');
const compWaitDiff = document.getElementById('comp-wait-diff');
const compSurgeTag = document.getElementById('comp-surge-tag');
const compBaseSurge = document.getElementById('comp-base-surge');
const compModelSurge = document.getElementById('comp-model-surge');
const hourlyChartContainer = document.getElementById('hourly-chart-container');

// Copilot Chat Elements
const copilotMessages = document.getElementById('copilot-messages');
const copilotForm = document.getElementById('copilot-form');
const copilotInput = document.getElementById('copilot-input');
const copilotSendBtn = document.getElementById('copilot-send-btn');
const clearChatBtn = document.getElementById('clear-chat-btn');
const ttsToggleBtn = document.getElementById('tts-toggle-btn');
const ttsIcon = document.getElementById('tts-icon');
const ttsLabel = document.getElementById('tts-label');
const copilotMicBtn = document.getElementById('copilot-mic-btn');
const copilotVoiceStatus = document.getElementById('copilot-voice-status');
const copilotVoiceStopBtn = document.getElementById('copilot-voice-stop-btn');
const voiceStatusLabel = document.getElementById('voice-status-label');

// City Demand
const allZonesList = document.getElementById('all-zones-list');
const zoneSearchInput = document.getElementById('zone-search-input');
const kpiTotalDemand = document.getElementById('kpi-total-demand');
const kpiSurgeCount = document.getElementById('kpi-surge-count');
const kpiTotalSupply = document.getElementById('kpi-total-supply');
const kpiEventsCount = document.getElementById('kpi-events-count');

// Active Dispatch Card
const activeDispatchCard = document.getElementById('active-dispatch-card');
const dispatchTargetName = document.getElementById('dispatch-target-name');
const dispatchEtaVal = document.getElementById('dispatch-eta-val');
const dispatchDistVal = document.getElementById('dispatch-dist-val');
const dispatchSurgeVal = document.getElementById('dispatch-surge-val');
const cancelDispatchBtn = document.getElementById('cancel-dispatch-btn');
const completeDispatchBtn = document.getElementById('complete-dispatch-btn');

// Map Controls
const mapRecenterBtn = document.getElementById('map-recenter-btn');
const mapThemeBtn = document.getElementById('map-theme-btn');
const mapFitBoundsBtn = document.getElementById('map-fit-bounds-btn');


// ============================================================================
// INITIALIZATION
// ============================================================================
document.addEventListener('DOMContentLoaded', async () => {
  setupEventListeners();
  await loadZonesCatalog();
  checkExistingSession();
});

function setupEventListeners() {
  loginForm.addEventListener('submit', handleLogin);
  logoutBtn.addEventListener('click', handleLogout);

  // Password visibility toggle
  togglePasswordBtn.addEventListener('click', () => {
    if (passwordInput.type === 'password') {
      passwordInput.type = 'text';
      togglePasswordBtn.textContent = 'Hide';
    } else {
      passwordInput.type = 'password';
      togglePasswordBtn.textContent = 'Show';
    }
  });

  // Demo driver cards in login
  document.querySelectorAll('.demo-driver-card').forEach((card) => {
    card.addEventListener('click', () => {
      const user = card.getAttribute('data-user');
      usernameInput.value = user;
      passwordInput.value = 'password123';
      handleLogin(new Event('submit'));
    });
  });

  // Tab switching (Sidebar drawer: For Me & City only)
  if (tabPersonalBtn) tabPersonalBtn.addEventListener('click', () => switchTab('personal'));
  if (tabOverallBtn) tabOverallBtn.addEventListener('click', () => switchTab('overall'));
  if (tabCopilotBtn) tabCopilotBtn.addEventListener('click', () => switchTab('copilot'));
  if (tabAnalyticsBtn) tabAnalyticsBtn.addEventListener('click', () => switchTab('analytics'));

  // Header Navbar Action Buttons (Sherpa & Impact on navbar only)
  if (headerCopilotBtn) {
    headerCopilotBtn.addEventListener('click', () => {
      if (state.currentTab === 'copilot') {
        switchTab('personal');
      } else {
        switchTab('copilot');
      }
    });
  }

  if (headerAnalyticsBtn) {
    headerAnalyticsBtn.addEventListener('click', () => {
      if (state.currentTab === 'analytics') {
        switchTab('personal');
      } else {
        switchTab('analytics');
      }
    });
  }

  // Side Panel Close / Return buttons
  const closeCopilotBtn = document.getElementById('close-copilot-btn');
  if (closeCopilotBtn) {
    closeCopilotBtn.addEventListener('click', () => switchTab('personal'));
  }

  const closeAnalyticsBtn = document.getElementById('close-analytics-btn');
  if (closeAnalyticsBtn) {
    closeAnalyticsBtn.addEventListener('click', () => switchTab('personal'));
  }

  if (analyticsDriverSelect) {
    analyticsDriverSelect.addEventListener('change', (e) => {
      handleDriverAnalyticsChange(e.target.value);
    });
  }

  // Copilot Chat listeners
  copilotForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const prompt = copilotInput.value.trim();
    if (prompt) {
      sendCopilotMessage(prompt);
      copilotInput.value = '';
    }
  });

  clearChatBtn.addEventListener('click', clearCopilotChat);

  // Text-to-Speech (TTS) Toggle
  if (ttsToggleBtn) {
    updateTTSButtonUI();
    ttsToggleBtn.addEventListener('click', () => {
      state.ttsEnabled = !state.ttsEnabled;
      localStorage.setItem('sherpa_tts_enabled', state.ttsEnabled);
      if (!state.ttsEnabled) {
        stopSpeaking();
      }
      updateTTSButtonUI();
    });
  }

  // Speech-to-Text (Microphone) listeners
  if (copilotMicBtn) {
    copilotMicBtn.addEventListener('click', toggleVoiceRecording);
  }

  if (copilotVoiceStopBtn) {
    copilotVoiceStopBtn.addEventListener('click', stopVoiceRecording);
  }

  document.querySelectorAll('.copilot-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      const prompt = chip.getAttribute('data-prompt');
      if (prompt) {
        switchTab('copilot');
        sendCopilotMessage(prompt);
      }
    });
  });

  // Zone selector in header
  currentZoneSelect.addEventListener('change', async (e) => {
    const newZone = e.target.value;
    await setDriverCurrentZone(newZone);
  });

  refreshPersonalBtn.addEventListener('click', async () => {
    refreshPersonalBtn.classList.add('spinning');
    await loadPersonalRecommendations();
    refreshPersonalBtn.classList.remove('spinning');
  });

  // City Search & Filters
  zoneSearchInput.addEventListener('input', () => filterCityZones());
  document.querySelectorAll('.filter-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('.filter-chip').forEach((c) => c.classList.remove('active'));
      chip.classList.add('active');
      filterCityZones();
    });
  });

  // Dispatch actions
  cancelDispatchBtn.addEventListener('click', cancelDispatch);
  completeDispatchBtn.addEventListener('click', completeDispatch);

  // Map controls
  mapRecenterBtn.addEventListener('click', centerOnDriver);
  mapThemeBtn.addEventListener('click', toggleMapTheme);
  mapFitBoundsBtn.addEventListener('click', fitAllZones);
}


// ============================================================================
// SESSION & AUTHENTICATION
// ============================================================================
function checkExistingSession() {
  const savedDriver = localStorage.getItem('uber_driver_session');
  if (savedDriver) {
    try {
      state.driver = JSON.parse(savedDriver);
      state.currentZone = state.driver.current_zone_id || 'Z06';
      showDashboard();
    } catch {
      localStorage.removeItem('uber_driver_session');
      showAuth();
    }
  } else {
    showAuth();
  }
}

async function handleLogin(e) {
  e.preventDefault();
  loginError.classList.add('hidden');
  loginSubmitBtn.disabled = true;
  loginSubmitBtn.textContent = 'Signing In...';

  const username = usernameInput.value.trim();
  const password = passwordInput.value;

  try {
    const response = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username_or_email: username,
        password: password,
      }),
    });

    if (!response.ok) {
      throw new Error('Authentication failed. Please check credentials.');
    }

    const data = await response.json();
    state.driver = data.driver;
    state.currentZone = data.driver.current_zone_id || 'Z06';
    localStorage.setItem('uber_driver_session', JSON.stringify(state.driver));

    showDashboard();
  } catch (err) {
    loginError.textContent = err.message || 'Error signing in. Try again.';
    loginError.classList.remove('hidden');
  } finally {
    loginSubmitBtn.disabled = false;
    loginSubmitBtn.textContent = 'Continue';
  }
}

function handleLogout() {
  localStorage.removeItem('uber_driver_session');
  state.driver = null;
  if (state.dispatchInterval) clearInterval(state.dispatchInterval);
  state.activeDispatch = null;
  showAuth();
}

function showAuth() {
  authView.classList.remove('hidden');
  dashboardView.classList.add('hidden');
}

async function showDashboard() {
  authView.classList.add('hidden');
  dashboardView.classList.remove('hidden');

  // Populate driver UI
  userNameDisplay.textContent = state.driver.name || 'Aditya Singh';
  userAvatarDisplay.textContent = state.driver.avatar || '👨🏽‍💼';
  userCarDisplay.textContent = state.driver.vehicle || 'Toyota Sedan';
  userRatingDisplay.innerHTML = `★ ${state.driver.rating ? state.driver.rating.toFixed(2) : '4.92'} • <span id="user-car">${state.driver.vehicle || 'Toyota Sedan'}</span>`;

  // Init Map if not yet created
  initMap();

  // Populate zone selector dropdown
  populateZoneSelector();

  // Load data
  await Promise.all([
    loadOverallCityDemand(),
    loadPersonalRecommendations(),
  ]);

  // Recenter map on driver
  centerOnDriver();
}


// ============================================================================
// DATA LOADING
// ============================================================================
async function loadZonesCatalog() {
  try {
    const res = await fetch('/api/zones');
    if (res.ok) {
      const data = await res.json();
      state.zonesCatalog = data;
      state.zonesCoordsMap = {};
      data.forEach((z) => {
        state.zonesCoordsMap[z.zone_id] = {
          lat: z.latitude || 12.9716,
          lon: z.longitude || 77.5946,
          name: z.zone_name,
        };
      });
    }
  } catch (err) {
    console.error('Failed to load zones catalog:', err);
  }
}

function populateZoneSelector() {
  currentZoneSelect.innerHTML = '';
  state.zonesCatalog.forEach((z) => {
    const opt = document.createElement('option');
    opt.value = z.zone_id;
    opt.textContent = `${z.zone_id} - ${z.zone_name}`;
    if (z.zone_id === state.currentZone) {
      opt.selected = true;
    }
    currentZoneSelect.appendChild(opt);
  });

  const currentZoneObj = state.zonesCatalog.find((z) => z.zone_id === state.currentZone);
  if (currentZoneObj) {
    currentZoneBadge.textContent = `${currentZoneObj.zone_id} ${currentZoneObj.zone_name}`;
  }
}

async function setDriverCurrentZone(newZoneId) {
  state.currentZone = newZoneId;
  if (state.driver) {
    state.driver.current_zone_id = newZoneId;
    localStorage.setItem('uber_driver_session', JSON.stringify(state.driver));
  }

  const currentZoneObj = state.zonesCatalog.find((z) => z.zone_id === newZoneId);
  if (currentZoneObj) {
    currentZoneBadge.textContent = `${currentZoneObj.zone_id} ${currentZoneObj.zone_name}`;
  }

  // Update driver marker on map
  updateDriverMarker();

  // Reload personalized recommendations
  await loadPersonalRecommendations();

  // Recenter
  centerOnDriver();
}

/**
 * Load overall city recommendations (Phase 4 & 5 endpoints)
 */
async function loadOverallCityDemand() {
  try {
    const res = await fetch('/recommendations/latest');
    if (!res.ok) throw new Error('Failed to fetch recommendations');
    const data = await res.json();
    state.cityRecommendations = data;

    // Update KPI tiles
    let totalDemand = 0;
    let shortageCount = 0;
    let totalDrivers = 0;

    data.zones.forEach((z) => {
      totalDemand += z.predicted_requests || 0;
      totalDrivers += z.available_drivers || 0;
      if (z.recommended_action === 'REPOSITION_IN' || (z.supply_gap && z.supply_gap >= 2)) {
        shortageCount += 1;
      }
    });

    kpiTotalDemand.textContent = totalDemand;
    kpiSurgeCount.textContent = shortageCount;
    kpiTotalSupply.textContent = totalDrivers;
    kpiEventsCount.textContent = '3 Live';

    // Model refresh label
    if (data.generated_at) {
      const timeStr = new Date(data.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      modelRefreshLabel.textContent = `Model Live (${timeStr})`;
    }

    renderCityZonesList(data.zones);
    renderMapZoneMarkers(data.zones);
  } catch (err) {
    console.error('Failed to load city demand:', err);
    allZonesList.innerHTML = `<div class="loading-state">Error loading recommendations: ${err.message}</div>`;
  }
}

/**
 * Load personalized recommendations for current driver location
 */
async function loadPersonalRecommendations() {
  personalCardsList.innerHTML = `
    <div class="loading-state">
      <div class="spinner"></div>
      <span>Computing optimal repositioning targets from ${state.currentZone}...</span>
    </div>
  `;

  try {
    const res = await fetch(`/api/recommendations/for-me?zone_id=${state.currentZone}&limit=6`);
    if (!res.ok) throw new Error('Failed to fetch personalized recommendations');
    const data = await res.json();
    state.personalRecommendations = data;

    renderPersonalCards(data.recommendations);
  } catch (err) {
    console.error('Failed to load personal recommendations:', err);
    personalCardsList.innerHTML = `<div class="loading-state">Error: ${err.message}</div>`;
  }
}


// ============================================================================
// UI RENDERING - CARDS & LISTS
// ============================================================================
function renderPersonalCards(recs) {
  if (!recs || recs.length === 0) {
    personalCardsList.innerHTML = `
      <div class="loading-state">
        <span>No urgent repositioning targets needed from this zone. Local demand is well-balanced.</span>
      </div>
    `;
    personalBadgeCount.textContent = '0';
    return;
  }

  personalBadgeCount.textContent = recs.length;
  personalCardsList.innerHTML = '';

  recs.forEach((rec, idx) => {
    const card = document.createElement('div');
    card.className = 'uber-reposition-card';
    card.setAttribute('data-zone-id', rec.zone_id);

    const isHighSurge = rec.supply_gap >= 3;
    const badgeText = rec.badge || (isHighSurge ? 'High Demand Surge' : 'Quick Reposition');
    const badgeClass = isHighSurge ? 'surge-badge' : 'quick-badge';
    const surgeMultiplier = (1.0 + (Math.max(rec.supply_gap, 1) * 0.15)).toFixed(1);

    card.innerHTML = `
      <div class="card-top-row">
        <div class="card-badge-row">
          <span class="rank-badge">#${idx + 1}</span>
          <span class="${badgeClass}">⚡ ${badgeText}</span>
        </div>
        <span class="card-eta-pill">⏱️ ${rec.travel_time_min}m (${rec.distance_km} km)</span>
      </div>

      <div class="card-zone-heading">
        <h4 class="card-zone-title">${rec.zone_id} ${rec.zone_name}</h4>
        <span class="card-zone-sub">Surge Estimate: <strong>${surgeMultiplier}x</strong> • Score: ${rec.opportunity_score}</span>
      </div>

      <div class="card-stats-grid">
        <div class="stat-cell">
          <span class="stat-cell-label">Driver Need</span>
          <span class="stat-cell-val shortage">+${rec.supply_gap} Drivers</span>
        </div>
        <div class="stat-cell">
          <span class="stat-cell-label">Forecast Demand</span>
          <span class="stat-cell-val demand">${rec.predicted_requests} Rides</span>
        </div>
        <div class="stat-cell">
          <span class="stat-cell-label">Active Fleet</span>
          <span class="stat-cell-val">${rec.available_drivers} Idle</span>
        </div>
      </div>

      <div class="card-reason-chips">
        ${(rec.reason_codes || []).slice(0, 3).map((c) => `<span class="reason-chip">${formatReason(c)}</span>`).join('')}
      </div>

      <div class="card-action-row">
        <button class="uber-btn-primary btn-sm btn-accept" style="flex: 2;">
          <span>Accept Reposition</span> ➔
        </button>
        <button class="uber-btn-secondary btn-preview" style="flex: 1;">
          <span>Map View</span>
        </button>
      </div>
    `;

    // Click card / preview
    card.addEventListener('click', (e) => {
      if (!e.target.closest('.btn-accept')) {
        previewZoneOnMap(rec.zone_id);
      }
    });

    // Accept button
    const acceptBtn = card.querySelector('.btn-accept');
    acceptBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      startDispatch(rec);
    });

    personalCardsList.appendChild(card);
  });
}

function renderCityZonesList(zones) {
  allZonesList.innerHTML = '';
  zones.forEach((z, idx) => {
    const item = document.createElement('div');
    item.className = 'city-zone-item';
    item.setAttribute('data-zone-id', z.zone_id);
    item.setAttribute('data-action', z.recommended_action);
    item.setAttribute('data-name', z.zone_name.toLowerCase());

    let actionClass = 'monitor';
    let actionText = 'Monitor';
    if (z.recommended_action === 'REPOSITION_IN') {
      actionClass = 'reposition-in';
      actionText = `+${z.supply_gap} Shortage`;
    } else if (z.recommended_action === 'REPOSITION_OUT') {
      actionClass = 'reposition-out';
      actionText = `${Math.abs(z.supply_gap)} Surplus`;
    }

    item.innerHTML = `
      <div class="zone-item-left">
        <div class="zone-rank-circle">#${idx + 1}</div>
        <div>
          <div class="zone-item-name">${z.zone_id} ${z.zone_name}</div>
          <div class="zone-item-sub">${z.available_drivers} drivers available</div>
        </div>
      </div>
      <div class="zone-item-right">
        <span class="zone-demand-num">${z.predicted_requests} reqs</span>
        <span class="zone-action-pill ${actionClass}">${actionText}</span>
      </div>
    `;

    item.addEventListener('click', () => {
      previewZoneOnMap(z.zone_id);
    });

    allZonesList.appendChild(item);
  });
}

function filterCityZones() {
  const query = zoneSearchInput.value.toLowerCase().trim();
  const activeChip = document.querySelector('.filter-chip.active');
  const filterType = activeChip ? activeChip.getAttribute('data-filter') : 'all';

  document.querySelectorAll('.city-zone-item').forEach((item) => {
    const name = item.getAttribute('data-name');
    const zid = item.getAttribute('data-zone-id').toLowerCase();
    const action = item.getAttribute('data-action');

    const matchesQuery = !query || name.includes(query) || zid.includes(query);
    let matchesFilter = true;

    if (filterType === 'shortage') {
      matchesFilter = action === 'REPOSITION_IN';
    } else if (filterType === 'surplus') {
      matchesFilter = action === 'REPOSITION_OUT';
    } else if (filterType === 'events') {
      // Show top demand zones
      matchesFilter = parseInt(item.querySelector('.zone-demand-num').textContent) > 20;
    }

    if (matchesQuery && matchesFilter) {
      item.style.display = 'flex';
    } else {
      item.style.display = 'none';
    }
  });
}

function switchTab(tab) {
  state.currentTab = tab;

  // Sidebar Segmented Tabs (For Me & City)
  if (tabPersonalBtn) tabPersonalBtn.classList.toggle('active', tab === 'personal');
  if (tabOverallBtn) tabOverallBtn.classList.toggle('active', tab === 'overall');
  if (tabCopilotBtn) tabCopilotBtn.classList.toggle('active', tab === 'copilot');
  if (tabAnalyticsBtn) tabAnalyticsBtn.classList.toggle('active', tab === 'analytics');

  // Header Navbar Action Buttons (Sherpa & Impact on navbar only)
  if (headerCopilotBtn) headerCopilotBtn.classList.toggle('active', tab === 'copilot');
  if (headerAnalyticsBtn) headerAnalyticsBtn.classList.toggle('active', tab === 'analytics');

  // Sidebar Panels
  if (panelPersonal) panelPersonal.classList.toggle('hidden', tab !== 'personal');
  if (panelOverall) panelOverall.classList.toggle('hidden', tab !== 'overall');
  if (panelCopilot) panelCopilot.classList.toggle('hidden', tab !== 'copilot');
  if (panelAnalytics) panelAnalytics.classList.toggle('hidden', tab !== 'analytics');

  if (tab === 'copilot') {
    if (state.chatHistory.length === 0) {
      initCopilotWelcome();
    }
    setTimeout(() => {
      if (copilotInput) copilotInput.focus();
      scrollChatToBottom();
    }, 100);
  } else if (tab === 'analytics') {
    if (!state.earningsAnalysis) {
      loadEarningsAnalysis();
    }
  }
}

// ============================================================================
// EARNINGS & COUNTERFACTUAL ROI ANALYSIS
// ============================================================================
async function loadEarningsAnalysis(driverId = null) {
  try {
    const url = driverId ? `/api/analysis/earnings?driver_id=${driverId}` : '/api/analysis/earnings';
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to load earnings analysis');
    const data = await res.json();
    state.earningsAnalysis = data;

    renderEarningsAnalysisUI(data);
  } catch (err) {
    console.error('Earnings analysis fetch failed:', err);
  }
}

function renderEarningsAnalysisUI(data) {
  if (!data || !data.summary) return;
  const s = data.summary;

  // Monthly hero
  if (analyticsMonthlyGain) analyticsMonthlyGain.textContent = Number(s.monthly_net_gain).toLocaleString('en-IN');
  if (analyticsShiftWith) analyticsShiftWith.textContent = `₹${Number(s.shift_model_earnings).toLocaleString('en-IN')} / shift`;
  if (analyticsShiftWithout) analyticsShiftWithout.textContent = `₹${Number(s.shift_base_earnings).toLocaleString('en-IN')} / shift`;

  // Comp tiles
  if (compEarningsPct) compEarningsPct.textContent = `+${s.shift_pct_gain}%`;
  if (compBaseEarn) compBaseEarn.textContent = `₹${Number(s.shift_base_earnings).toLocaleString('en-IN')}`;
  if (compModelEarn) compModelEarn.textContent = `₹${Number(s.shift_model_earnings).toLocaleString('en-IN')}`;
  if (compEarnDiff) compEarnDiff.textContent = `+₹${Number(s.shift_net_gain).toLocaleString('en-IN')} per shift`;

  if (compTripsPct) compTripsPct.textContent = `+${Math.round(((s.model_trips_per_shift - s.base_trips_per_shift) / s.base_trips_per_shift) * 100)}%`;
  if (compBaseTrips) compBaseTrips.textContent = `${s.base_trips_per_shift} trips`;
  if (compModelTrips) compModelTrips.textContent = `${s.model_trips_per_shift} trips`;
  if (compTripsDiff) compTripsDiff.textContent = `+${(s.model_trips_per_shift - s.base_trips_per_shift).toFixed(1)} rides / shift`;

  if (compWaitPct) compWaitPct.textContent = `-${s.idle_reduction_pct}%`;
  if (compBaseWait) compBaseWait.textContent = `${s.idle_wait_time_without} min/hr`;
  if (compModelWait) compModelWait.textContent = `${s.idle_wait_time_with} min/hr`;
  if (compWaitDiff) compWaitDiff.textContent = `${(s.idle_wait_time_without - s.idle_wait_time_with).toFixed(1)} min less idle wait`;

  if (compBaseSurge) compBaseSurge.textContent = s.surge_capture_rate_without;
  if (compModelSurge) compModelSurge.textContent = s.surge_capture_rate_with;

  // 24-Hour hourly chart
  if (data.hourly_chart && hourlyChartContainer) {
    renderHourlyChart(data.hourly_chart);
  }
}

function renderHourlyChart(hourlyData) {
  if (!hourlyChartContainer || !hourlyData) return;
  hourlyChartContainer.innerHTML = '';

  const maxVal = Math.max(...hourlyData.map(h => Math.max(h.without_model, h.with_model))) || 700;

  hourlyData.forEach(h => {
    const col = document.createElement('div');
    col.className = 'hourly-col';

    const basePct = Math.max(8, Math.round((h.without_model / maxVal) * 100));
    const modelPct = Math.max(12, Math.round((h.with_model / maxVal) * 100));

    col.innerHTML = `
      <div class="hourly-tooltip">
        <strong>${h.label}</strong><br>
        CommitCon: ₹${h.with_model}<br>
        Without: ₹${h.without_model}<br>
        Gain: +₹${h.difference} (+${h.pct_increase}%)
      </div>
      <div class="hourly-col-bars">
        <div class="bar-sub bar-base" style="height: ${basePct}%;" title="Without Model: ₹${h.without_model}"></div>
        <div class="bar-sub bar-model" style="height: ${modelPct}%;" title="With CommitCon: ₹${h.with_model}"></div>
      </div>
      <span class="hour-label">${h.hour % 3 === 0 ? h.label.split(':')[0] : ''}</span>
    `;

    hourlyChartContainer.appendChild(col);
  });
}

function handleDriverAnalyticsChange(driverKey) {
  if (!state.earningsAnalysis) return;
  const profiles = state.earningsAnalysis.driver_profiles || {};

  if (driverKey === 'ALL' || !profiles[driverKey]) {
    if (driverPersonalizedCallout) {
      driverPersonalizedCallout.classList.add('hidden');
      driverPersonalizedCallout.innerHTML = '';
    }
    renderEarningsAnalysisUI(state.earningsAnalysis);
    return;
  }

  const p = profiles[driverKey];
  if (driverPersonalizedCallout) {
    driverPersonalizedCallout.classList.remove('hidden');
    driverPersonalizedCallout.innerHTML = `
      <div><strong>👤 ${p.name}</strong> • Base: ${p.home_zone}</div>
      <div class="callout-row">💰 Projected Shift: <strong>₹${p.shift_with_model.toLocaleString('en-IN')}</strong> (vs ₹${p.shift_without_model.toLocaleString('en-IN')} baseline)</div>
      <div class="callout-row">🚀 Monthly Extra Cash: <strong class="text-green">+₹${p.monthly_gain.toLocaleString('en-IN')}</strong></div>
      <div class="callout-row">⚡ Top Surge Target: <strong>${p.top_surge_zone}</strong> (${p.surge_captures} surge rate)</div>
      <div class="callout-row">⏱️ Idle Time Reduction: <strong>${p.idle_reduction_mins}</strong></div>
    `;
  }
}

// ============================================================================
// SHERPA AI (DRIVER CHATBOT)
// ============================================================================
function initCopilotWelcome() {
  const driverName = state.driver ? state.driver.name.split(' ')[0] : 'Driver';
  const welcomeText = `Hello ${driverName}! I'm **Sherpa**, your AI driver assistant connected to our GPU inference service (\`project-driver:latest\`).

I have live context on your position in **${state.currentZone}** and real-time demand forecasts across all 20 city zones.

Ask me anything, like:
* **"Where should I reposition right now?"**
* **"Why is Z02 Airport recommended?"**
* **"Which zone has the fastest travel time under 15 minutes?"**`;

  appendCopilotMessage('assistant', welcomeText, false);
}

function appendCopilotMessage(role, text, save = true) {
  const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  if (save) {
    state.chatHistory.push({ role, content: text });
    try {
      const storageKey = 'copilot_history_' + (state.driver ? state.driver.id : 'demo');
      localStorage.setItem(storageKey, JSON.stringify(state.chatHistory.slice(-12)));
    } catch {}
  }

  const msgDiv = document.createElement('div');
  msgDiv.className = `chat-msg ${role === 'user' ? 'user' : 'bot'}`;

  const avatar = role === 'user' ? (state.driver ? state.driver.avatar : '👨🏽‍💼') : '🧭';
  const formattedHtml = formatMarkdown(text);

  if (role === 'assistant') {
    msgDiv.innerHTML = `
      <div class="chat-msg-avatar">${avatar}</div>
      <div class="chat-bubble">
        ${formattedHtml}
        <div class="chat-bubble-footer">
          <span class="chat-time">${timeStr}</span>
          <button type="button" class="msg-speak-btn" title="Listen to this message">
            <span class="speak-icon">🔊</span>
            <span>Listen</span>
          </button>
        </div>
      </div>
    `;

    const speakBtn = msgDiv.querySelector('.msg-speak-btn');
    if (speakBtn) {
      speakBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (speakBtn.classList.contains('speaking')) {
          stopSpeaking();
        } else {
          speakText(text, speakBtn);
        }
      });
    }
  } else {
    msgDiv.innerHTML = `
      <div class="chat-msg-avatar">${avatar}</div>
      <div class="chat-bubble">
        ${formattedHtml}
        <span class="chat-time">${timeStr}</span>
      </div>
    `;
  }

  copilotMessages.appendChild(msgDiv);
  scrollChatToBottom();
}

function formatMarkdown(text) {
  if (!text) return '';
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code style="background:#E2E8F0;padding:2px 4px;border-radius:4px;font-size:11px;">$1</code>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n\* /g, '<br>• ')
    .replace(/\n/g, '<br>');

  return `<p>${html}</p>`;
}

async function sendCopilotMessage(prompt) {
  appendCopilotMessage('user', prompt, true);

  // Show typing indicator
  const typingDiv = document.createElement('div');
  typingDiv.className = 'chat-msg bot copilot-typing-msg';
  typingDiv.innerHTML = `
    <div class="chat-msg-avatar">🧭</div>
    <div class="copilot-typing">
      <span>Sherpa is analyzing fleet data</span>
      <div class="typing-dots"><span></span><span></span><span></span></div>
    </div>
  `;
  copilotMessages.appendChild(typingDiv);
  scrollChatToBottom();

  copilotSendBtn.disabled = true;

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        driver_id: state.driver ? state.driver.id : 'DRV_101',
        driver_prompt: prompt,
        current_zone_id: state.currentZone,
        history: state.chatHistory.slice(-8),
      }),
    });

    if (!res.ok) {
      throw new Error(`Inference returned HTTP ${res.status}`);
    }

    const data = await res.json();
    typingDiv.remove();
    appendCopilotMessage('assistant', data.answer, true);

    // Text-to-Speech: Auto voice response if enabled
    if (state.ttsEnabled) {
      speakText(data.answer);
    }
  } catch (err) {
    typingDiv.remove();
    const errMsg = `⚠️ Could not reach Sherpa (${err.message}). Live model recommendation: check **Z02 Airport** or **Z07 Railway Station** for high demand.`;
    appendCopilotMessage('assistant', errMsg, false);
    if (state.ttsEnabled) {
      speakText(errMsg);
    }
  } finally {
    copilotSendBtn.disabled = false;
  }
}

function clearCopilotChat() {
  stopSpeaking();
  stopVoiceRecording();
  state.chatHistory = [];
  try {
    const storageKey = 'copilot_history_' + (state.driver ? state.driver.id : 'demo');
    localStorage.removeItem(storageKey);
  } catch {}
  copilotMessages.innerHTML = '';
  initCopilotWelcome();
}

function scrollChatToBottom() {
  copilotMessages.scrollTop = copilotMessages.scrollHeight;
}

// ============================================================================
// VOICE INPUT (SPEECH-TO-TEXT) & AUDIO OUTPUT (TEXT-TO-SPEECH)
// ============================================================================

function updateTTSButtonUI() {
  if (!ttsToggleBtn) return;
  if (state.ttsEnabled) {
    ttsToggleBtn.classList.add('active');
    ttsToggleBtn.classList.remove('muted');
    ttsToggleBtn.setAttribute('title', 'Voice Responses: Enabled (Click to Mute)');
    if (ttsIcon) ttsIcon.textContent = '🔊';
    if (ttsLabel) ttsLabel.textContent = 'Voice ON';
  } else {
    ttsToggleBtn.classList.remove('active');
    ttsToggleBtn.classList.add('muted');
    ttsToggleBtn.setAttribute('title', 'Voice Responses: Muted (Click to Unmute)');
    if (ttsIcon) ttsIcon.textContent = '🔇';
    if (ttsLabel) ttsLabel.textContent = 'Voice OFF';
  }
}

function cleanTextForSpeech(raw) {
  if (!raw) return '';
  return raw
    .replace(/[*_#`~>]/g, '')                // Strip markdown formatting symbols
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')  // Strip markdown links
    .replace(/[\u{1F300}-\u{1FAFF}]/gu, '')   // Strip emojis
    .replace(/\s+/g, ' ')                    // Collapse spaces
    .trim();
}

function speakText(rawText, targetBtn = null) {
  if (!('speechSynthesis' in window)) return;

  // Stop any active speech before starting new speech
  stopSpeaking();

  const spokenText = cleanTextForSpeech(rawText);
  if (!spokenText) return;

  const utterance = new SpeechSynthesisUtterance(spokenText);
  utterance.lang = 'en-IN';
  utterance.rate = 1.05;
  utterance.pitch = 1.0;

  // Choose a clean English voice if available
  const voices = window.speechSynthesis.getVoices();
  const naturalVoice = voices.find(v => (v.lang === 'en-IN' || v.lang === 'en-GB' || v.lang === 'en-US') && !v.name.includes('whisper'));
  if (naturalVoice) {
    utterance.voice = naturalVoice;
  }

  if (targetBtn) {
    targetBtn.classList.add('speaking');
    targetBtn.innerHTML = '<span class="speak-icon">🔊</span><span>Playing...</span>';
  }

  utterance.onend = () => {
    if (targetBtn) {
      targetBtn.classList.remove('speaking');
      targetBtn.innerHTML = '<span class="speak-icon">🔊</span><span>Listen</span>';
    }
  };

  utterance.onerror = () => {
    if (targetBtn) {
      targetBtn.classList.remove('speaking');
      targetBtn.innerHTML = '<span class="speak-icon">🔊</span><span>Listen</span>';
    }
  };

  window.speechSynthesis.speak(utterance);
}

function stopSpeaking() {
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
  }
  document.querySelectorAll('.msg-speak-btn.speaking').forEach(btn => {
    btn.classList.remove('speaking');
    btn.innerHTML = '<span class="speak-icon">🔊</span><span>Listen</span>';
  });
}

function toggleVoiceRecording() {
  if (state.isRecordingVoice) {
    stopVoiceRecording();
  } else {
    startVoiceRecording();
  }
}

function startVoiceRecording() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    alert('Voice recognition is not supported in this browser. Please type into the chat.');
    return;
  }

  // Stop any ongoing voice output when driver is about to speak
  stopSpeaking();

  try {
    state.recognition = new SpeechRecognition();
    state.recognition.lang = 'en-IN';
    state.recognition.continuous = false;
    state.recognition.interimResults = true;

    let finalTranscript = '';

    state.recognition.onstart = () => {
      state.isRecordingVoice = true;
      if (copilotMicBtn) {
        copilotMicBtn.classList.add('listening');
        copilotMicBtn.setAttribute('title', 'Listening... Tap to stop');
      }
      if (copilotVoiceStatus) copilotVoiceStatus.classList.remove('hidden');
      if (voiceStatusLabel) voiceStatusLabel.textContent = 'Listening to your voice... Speak now';
    };

    state.recognition.onresult = (event) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        } else {
          interim += event.results[i][0].transcript;
        }
      }
      const currentText = (finalTranscript || interim).trim();
      copilotInput.value = currentText;
      if (voiceStatusLabel) {
        voiceStatusLabel.textContent = currentText ? `"${currentText}"` : 'Listening... Speak now';
      }
    };

    state.recognition.onerror = (event) => {
      console.warn('Speech recognition error:', event.error);
      if (event.error === 'not-allowed') {
        alert('Microphone access was denied. Please allow microphone permissions in your browser address bar.');
      }
      stopVoiceRecording();
    };

    state.recognition.onend = () => {
      const recognized = copilotInput.value.trim();
      stopVoiceRecording();

      // Automatically send the driver's spoken prompt to Sherpa!
      if (recognized) {
        sendCopilotMessage(recognized);
        copilotInput.value = '';
      }
    };

    state.recognition.start();
  } catch (err) {
    console.error('Failed to start speech recognition:', err);
    stopVoiceRecording();
  }
}

function stopVoiceRecording() {
  state.isRecordingVoice = false;
  if (copilotMicBtn) {
    copilotMicBtn.classList.remove('listening');
    copilotMicBtn.setAttribute('title', 'Speak to Sherpa (Voice Input)');
  }
  if (copilotVoiceStatus) {
    copilotVoiceStatus.classList.add('hidden');
  }
  if (state.recognition) {
    try {
      state.recognition.stop();
    } catch {}
    state.recognition = null;
  }
}

function formatReason(code) {
  const map = {
    CRITICAL_DRIVER_SHORTAGE: 'Severe Driver Shortage',
    DRIVER_SHORTAGE: 'High Passenger Gap',
    HIGH_FORECAST_DEMAND: 'Peak Demand Forecast',
    EVENT_NEARBY: 'Live Event Nearby',
    FAST_TRAVEL_TIME: 'Fast ETA (<15m)',
    PEAK_HOUR: 'Peak Commute Hour',
    HIGH_WAIT_TIME: 'High Wait Times',
  };
  return map[code] || code.replace(/_/g, ' ');
}


// ============================================================================
// MAP VISUALIZATION (LEAFLET INTEGRATION)
// ============================================================================
// Map boundaries matching static traffic image (lat 12.83 to 13.23, lon 77.46 to 77.76)
const TRAFFIC_BOUNDS = [[12.83, 77.46], [13.23, 77.76]];

function initMap() {
  if (state.map) return; // already initialized

  // Default coordinate: Downtown Bengaluru
  const centerLat = 12.9716;
  const centerLon = 77.5946;

  // Initialize Leaflet Map
  state.map = L.map('map', {
    center: [centerLat, centerLon],
    zoom: 12,
    minZoom: 10,
    maxZoom: 18,
    zoomControl: false,
    maxBounds: [[12.75, 77.35], [13.35, 77.88]],
  });

  // Custom Zoom Control on bottom-left
  L.control.zoom({ position: 'bottomleft' }).addTo(state.map);

  // 1. Base OpenStreetMap layer (free, open, no API key required)
  state.osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors',
  }).addTo(state.map);

  // 2. Custom Pane for Traffic Overlay (below vectors, markers & popups)
  state.map.createPane('trafficPane');
  state.map.getPane('trafficPane').style.zIndex = 250;

  // 3. Static Traffic View Map Image (Photorealistic traffic conditions, no API key)
  state.trafficOverlay = L.imageOverlay('/static/traffic_map.png', TRAFFIC_BOUNDS, {
    opacity: 0.96,
    interactive: false,
    pane: 'trafficPane',
  }).addTo(state.map);

  state.isTrafficView = true;

  // Render initial driver marker
  updateDriverMarker();
}

function toggleMapTheme() {
  if (state.isTrafficView) {
    // Hide static traffic overlay -> Reveal pure OpenStreetMap
    if (state.trafficOverlay && state.map.hasLayer(state.trafficOverlay)) {
      state.map.removeLayer(state.trafficOverlay);
    }
    state.isTrafficView = false;
    mapThemeBtn.querySelector('.ctrl-icon').textContent = '🚦';
    mapThemeBtn.querySelector('.ctrl-tooltip').textContent = 'Traffic View';
  } else {
    // Show static traffic overlay
    if (state.trafficOverlay && !state.map.hasLayer(state.trafficOverlay)) {
      state.trafficOverlay.addTo(state.map);
    }
    state.isTrafficView = true;
    mapThemeBtn.querySelector('.ctrl-icon').textContent = '🗺️';
    mapThemeBtn.querySelector('.ctrl-tooltip').textContent = 'Street Map';
  }
}

function getZoneLatLng(zoneId) {
  if (state.zonesCoordsMap[zoneId]) {
    return [state.zonesCoordsMap[zoneId].lat, state.zonesCoordsMap[zoneId].lon];
  }
  return [12.9716, 77.5946];
}

/**
 * Driver vehicle marker with glowing animated pulse ring
 */
function updateDriverMarker() {
  if (!state.map) return;

  const [lat, lon] = getZoneLatLng(state.currentZone);

  if (state.driverMarker) {
    state.driverMarker.setLatLng([lat, lon]);
  } else {
    const driverIcon = L.divIcon({
      className: 'custom-driver-marker',
      html: `
        <div class="driver-marker-pulse"></div>
        <div class="driver-marker-car">🚗</div>
      `,
      iconSize: [48, 48],
      iconAnchor: [24, 24],
    });

    state.driverMarker = L.marker([lat, lon], {
      icon: driverIcon,
      zIndexOffset: 1000,
    }).addTo(state.map);

    state.driverMarker.bindTooltip(`<strong>My Location</strong><br>${state.currentZone}`, {
      direction: 'top',
      offset: [0, -20],
      permanent: false,
    });
  }
}

/**
 * Render all 20 zone markers with demand status rings
 */
function renderMapZoneMarkers(zones) {
  if (!state.map || !zones) return;

  // Clear existing
  Object.values(state.zoneMarkers).forEach((marker) => {
    state.map.removeLayer(marker);
  });
  state.zoneMarkers = {};

  zones.forEach((z) => {
    const coords = getZoneLatLng(z.zone_id);
    let colorClass = 'orange';
    if (z.recommended_action === 'REPOSITION_IN') colorClass = 'red';
    else if (z.recommended_action === 'REPOSITION_OUT') colorClass = 'green';

    const pinHtml = `
      <div class="zone-marker-pin ${colorClass}">
        <span>${z.zone_id}</span>
      </div>
    `;

    const icon = L.divIcon({
      className: 'custom-zone-marker',
      html: pinHtml,
      iconSize: [40, 24],
      iconAnchor: [20, 12],
    });

    const marker = L.marker(coords, { icon: icon, zIndexOffset: 500 }).addTo(state.map);

    // Uber Popup
    const popupContent = `
      <div class="uber-popup">
        <h4>${z.zone_id} • ${z.zone_name}</h4>
        <div class="popup-sub">${z.recommended_action.replace(/_/g, ' ')} • Status</div>
        <div class="popup-stats">
          <div>
            <div class="popup-stat-label">Forecast Demand</div>
            <div class="popup-stat-value">${z.predicted_requests} rides</div>
          </div>
          <div>
            <div class="popup-stat-label">Driver Gap</div>
            <div class="popup-stat-value text-surge">${z.supply_gap > 0 ? '+' : ''}${z.supply_gap}</div>
          </div>
        </div>
        <button class="popup-reposition-btn" onclick="window.dispatchToZone('${z.zone_id}')">
          Reposition Here ➔
        </button>
      </div>
    `;

    marker.bindPopup(popupContent);
    state.zoneMarkers[z.zone_id] = marker;
  });
}

function previewZoneOnMap(zoneId) {
  if (!state.map) return;
  const coords = getZoneLatLng(zoneId);

  // Highlight card
  document.querySelectorAll('.uber-reposition-card').forEach((c) => {
    c.classList.toggle('active-target', c.getAttribute('data-zone-id') === zoneId);
  });

  // Pan to zone and open popup
  state.map.flyTo(coords, 14, { duration: 1.2 });
  if (state.zoneMarkers[zoneId]) {
    setTimeout(() => {
      state.zoneMarkers[zoneId].openPopup();
    }, 1200);
  }

  // Draw preview polyline
  drawRouteLine(state.currentZone, zoneId, false);
}

function centerOnDriver() {
  if (!state.map) return;
  const coords = getZoneLatLng(state.currentZone);
  state.map.flyTo(coords, 13, { duration: 1.0 });
}

function fitAllZones() {
  if (!state.map || state.zonesCatalog.length === 0) return;
  const latLngs = state.zonesCatalog.map((z) => [z.latitude || 12.9716, z.longitude || 77.5946]);
  state.map.fitBounds(L.latLngBounds(latLngs), { padding: [50, 50] });
}

/**
 * Draw animated routing line between driver location and target zone
 */
function drawRouteLine(startZoneId, targetZoneId, isActiveNav = true) {
  if (!state.map) return;

  if (state.routePolyline) {
    state.map.removeLayer(state.routePolyline);
    state.routePolyline = null;
  }

  const startCoords = getZoneLatLng(startZoneId);
  const endCoords = getZoneLatLng(targetZoneId);

  // Route styling
  const color = isActiveNav ? '#276EF1' : '#000000';
  const dashArray = isActiveNav ? null : '6, 8';

  state.routePolyline = L.polyline([startCoords, endCoords], {
    color: color,
    weight: 4,
    opacity: 0.85,
    dashArray: dashArray,
    lineCap: 'round',
  }).addTo(state.map);

  // Fit bounds to show entire route
  state.map.fitBounds(state.routePolyline.getBounds(), {
    padding: [60, 60],
    maxZoom: 14,
  });
}


// ============================================================================
// DISPATCH & REPOSITION NAVIGATION
// ============================================================================
async function startDispatch(rec) {
  try {
    const res = await fetch('/api/drivers/accept-reposition', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        driver_id: state.driver.id || 'DRV_101',
        destination_zone_id: rec.zone_id,
      }),
    });

    if (!res.ok) throw new Error('Dispatch failed');

    state.activeDispatch = {
      destination_zone_id: rec.zone_id,
      zone_name: rec.zone_name,
      eta_min: rec.travel_time_min,
      distance_km: rec.distance_km,
      startTime: Date.now(),
    };

    // Show Active Dispatch Card
    dispatchTargetName.textContent = `Navigating to ${rec.zone_id} ${rec.zone_name}`;
    dispatchEtaVal.textContent = `${rec.travel_time_min} mins`;
    dispatchDistVal.textContent = `${rec.distance_km} km`;
    dispatchSurgeVal.textContent = `⚡ ${(1.0 + (rec.supply_gap * 0.15)).toFixed(1)}x`;
    activeDispatchCard.classList.remove('hidden');

    // Draw active navigation route
    drawRouteLine(state.currentZone, rec.zone_id, true);

    // Focus map on route
    previewZoneOnMap(rec.zone_id);

    // Start progress simulation
    simulateDispatchProgress(rec.travel_time_min);
  } catch (err) {
    alert(`Could not start reposition dispatch: ${err.message}`);
  }
}

function simulateDispatchProgress(totalMins) {
  if (state.dispatchInterval) clearInterval(state.dispatchInterval);
  let remainingSecs = totalMins * 60;
  const progressFill = document.getElementById('dispatch-progress-fill');

  state.dispatchInterval = setInterval(() => {
    remainingSecs -= 5; // fast forward simulation
    if (remainingSecs <= 0) {
      clearInterval(state.dispatchInterval);
      dispatchEtaVal.textContent = 'Arrived!';
      progressFill.style.width = '100%';
    } else {
      const minsLeft = Math.ceil(remainingSecs / 60);
      dispatchEtaVal.textContent = `${minsLeft} mins`;
    }
  }, 1000);
}

function cancelDispatch() {
  if (state.dispatchInterval) clearInterval(state.dispatchInterval);
  state.activeDispatch = null;
  activeDispatchCard.classList.add('hidden');

  if (state.routePolyline) {
    state.map.removeLayer(state.routePolyline);
    state.routePolyline = null;
  }

  centerOnDriver();
}

async function completeDispatch() {
  if (!state.activeDispatch) return;
  const targetZone = state.activeDispatch.destination_zone_id;
  cancelDispatch();

  // Move driver to the new zone
  currentZoneSelect.value = targetZone;
  await setDriverCurrentZone(targetZone);

  alert(`You have arrived at ${targetZone}! Your status is Online in the high-demand surge area.`);
}

// Global hook for popup clicks
window.dispatchToZone = function (zoneId) {
  const z = state.zonesCatalog.find((item) => item.zone_id === zoneId);
  const rec = {
    zone_id: zoneId,
    zone_name: z ? z.zone_name : `Zone ${zoneId}`,
    travel_time_min: 10,
    distance_km: 5.2,
    supply_gap: 5,
  };
  startDispatch(rec);
};
