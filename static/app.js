/**
 * CommitCon Driver Portal - Frontend State Management & API Integration
 */

// Application State
const state = {
  driver: null,
  currentZone: 'Z06',
  allZones: [],
  cityRecommendations: null,
  personalRecommendations: null,
  activeNavigation: null,
};

// DOM Elements
const authView = document.getElementById('auth-view');
const dashboardView = document.getElementById('dashboard-view');
const loginForm = document.getElementById('login-form');
const usernameInput = document.getElementById('username');
const passwordInput = document.getElementById('password');
const loginError = document.getElementById('login-error');
const logoutBtn = document.getElementById('logout-btn');

const tabOverallBtn = document.getElementById('tab-overall-btn');
const tabPersonalBtn = document.getElementById('tab-personal-btn');
const viewOverall = document.getElementById('view-overall');
const viewPersonal = document.getElementById('view-personal');

const currentZoneSelect = document.getElementById('current-zone-select');
const userNameDisplay = document.getElementById('user-name');
const userAvatarDisplay = document.getElementById('user-avatar');
const userCarDisplay = document.getElementById('user-car');
const driverStatusDisplay = document.getElementById('driver-status');
const generatedTimestamp = document.getElementById('generated-timestamp');

const totalDemandKpi = document.getElementById('total-demand-kpi');
const surgeZonesKpi = document.getElementById('surge-zones-kpi');
const totalSupplyKpi = document.getElementById('total-supply-kpi');
const activeEventsKpi = document.getElementById('active-events-kpi');
const zonesTableBody = document.getElementById('zones-table-body');
const refreshDemandBtn = document.getElementById('refresh-demand-btn');

const personalCurrentZoneName = document.getElementById('personal-current-zone-name');
const personalCardsContainer = document.getElementById('personal-cards-container');
const personalCountBadge = document.getElementById('personal-count-badge');

const navAlert = document.getElementById('nav-alert');
const navTitle = document.getElementById('nav-title');
const navDesc = document.getElementById('nav-desc');
const cancelNavBtn = document.getElementById('cancel-nav-btn');

// ============================================================================
// INITIALIZATION
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  checkExistingSession();
});

function setupEventListeners() {
  loginForm.addEventListener('submit', handleLogin);
  logoutBtn.addEventListener('click', handleLogout);

  // Demo driver chips
  document.querySelectorAll('.demo-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      const user = chip.getAttribute('data-user');
      usernameInput.value = user;
      passwordInput.value = 'password123';
      handleLogin(new Event('submit'));
    });
  });

  // Tab switching
  tabOverallBtn.addEventListener('click', () => switchTab('overall'));
  tabPersonalBtn.addEventListener('click', () => switchTab('personal'));

  // Zone selector change
  currentZoneSelect.addEventListener('change', async (e) => {
    state.currentZone = e.target.value;
    if (state.driver) {
      state.driver.current_zone_id = state.currentZone;
      localStorage.setItem('commitcon_driver', JSON.stringify(state.driver));
    }
    await loadPersonalRecommendations();
  });

  refreshDemandBtn.addEventListener('click', () => {
    loadOverallCityDemand();
  });

  cancelNavBtn.addEventListener('click', () => {
    state.activeNavigation = null;
    navAlert.classList.add('hidden');
    driverStatusDisplay.textContent = 'Online • Accepting Rides';
    driverStatusDisplay.parentElement.style.background = 'var(--success-bg)';
  });
}

// ============================================================================
// AUTHENTICATION
// ============================================================================
function checkExistingSession() {
  const savedDriver = localStorage.getItem('commitcon_driver');
  if (savedDriver) {
    try {
      state.driver = JSON.parse(savedDriver);
      state.currentZone = state.driver.current_zone_id || 'Z06';
      showDashboard();
    } catch (e) {
      localStorage.removeItem('commitcon_driver');
    }
  }
}

async function handleLogin(e) {
  if (e) e.preventDefault();
  loginError.classList.add('hidden');

  const username = usernameInput.value.trim();
  const password = passwordInput.value.trim();

  if (!username || !password) {
    showLoginError('Please enter your email or phone number and password.');
    return;
  }

  try {
    const response = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username_or_email: username, password }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Authentication failed');
    }

    const data = await response.json();
    state.driver = data.driver;
    state.currentZone = data.driver.current_zone_id || 'Z06';
    localStorage.setItem('commitcon_driver', JSON.stringify(state.driver));

    showDashboard();
  } catch (err) {
    showLoginError(err.message || 'Unable to connect to server. Please try again.');
  }
}

function showLoginError(msg) {
  loginError.textContent = msg;
  loginError.classList.remove('hidden');
}

function handleLogout() {
  state.driver = null;
  localStorage.removeItem('commitcon_driver');
  dashboardView.classList.add('hidden');
  authView.classList.remove('hidden');
}

function showDashboard() {
  authView.classList.add('hidden');
  dashboardView.classList.remove('hidden');

  // Populate driver profile
  userNameDisplay.textContent = state.driver.name;
  userAvatarDisplay.textContent = state.driver.avatar || '👨🏽';
  userCarDisplay.textContent = state.driver.vehicle || 'Toyota Sedan (KA-01-AB-1234)';

  // Populate all zones into dropdown and load data
  loadZoneList().then(() => {
    loadOverallCityDemand();
    loadPersonalRecommendations();
  });
}

// ============================================================================
// DATA FETCHING
// ============================================================================
async function loadZoneList() {
  try {
    const res = await fetch('/api/zones');
    if (res.ok) {
      state.allZones = await res.json();
      currentZoneSelect.innerHTML = '';
      state.allZones.forEach((z) => {
        const opt = document.createElement('option');
        opt.value = z.zone_id;
        opt.textContent = `${z.zone_id} - ${z.zone_name}`;
        if (z.zone_id === state.currentZone) {
          opt.selected = true;
        }
        currentZoneSelect.appendChild(opt);
      });
    }
  } catch (e) {
    console.error('Failed to load zones list', e);
  }
}

async function loadOverallCityDemand() {
  try {
    refreshDemandBtn.textContent = '⏳ Loading...';
    const res = await fetch('/recommendations/latest');
    if (!res.ok) throw new Error('Could not fetch recommendations');
    const data = await res.json();
    state.cityRecommendations = data;

    // Update timestamp
    const date = new Date(data.generated_at);
    generatedTimestamp.textContent = `Live Model Predictions • Updated ${date.toLocaleTimeString()} (Refreshes every 15m)`;

    // Calculate KPI summaries
    const totalRequests = data.zones.reduce((sum, z) => sum + z.predicted_requests, 0);
    const totalIdleDrivers = data.zones.reduce((sum, z) => sum + z.available_drivers, 0);
    const surgeZonesCount = data.summary.reposition_in || 0;

    totalDemandKpi.textContent = totalRequests;
    surgeZonesKpi.textContent = surgeZonesCount;
    totalSupplyKpi.textContent = totalIdleDrivers;
    activeEventsKpi.textContent = '6 Active';

    // Render Table
    renderCityDemandTable(data.zones);
  } catch (err) {
    console.error('Error fetching city demand:', err);
  } finally {
    refreshDemandBtn.textContent = '🔄 Refresh Data';
  }
}

function renderCityDemandTable(zones) {
  zonesTableBody.innerHTML = '';

  // Sort by highest predicted requests first so driver sees where the action is
  const sortedByDemand = [...zones].sort((a, b) => b.predicted_requests - a.predicted_requests);
  const maxRequests = Math.max(...zones.map((z) => z.predicted_requests), 1);

  sortedByDemand.forEach((zone, index) => {
    const tr = document.createElement('tr');

    const fillPercent = Math.min(100, Math.round((zone.predicted_requests / maxRequests) * 100));
    let demandLevel = 'Normal';
    let fillClass = 'normal';
    let badgeClass = 'status-pill steady';

    if (zone.predicted_requests >= 12) {
      demandLevel = '🔥 High Demand';
      fillClass = 'high';
      badgeClass = 'status-pill surge';
    } else if (zone.predicted_requests >= 6) {
      demandLevel = '⚡ Moderate';
      fillClass = 'medium';
      badgeClass = 'status-pill moderate';
    }

    // Supply gap presentation
    let gapHtml = `<span class="gap-pill balanced">Balanced (0)</span>`;
    if (zone.supply_gap > 0) {
      gapHtml = `<span class="gap-pill shortage">Shortage (+${zone.supply_gap} needed)</span>`;
    } else if (zone.supply_gap < 0) {
      gapHtml = `<span class="gap-pill surplus">Surplus (${Math.abs(zone.supply_gap)} excess)</span>`;
    }

    // Event tag
    const hasEvent = zone.reason_codes.includes('EVENT_NEARBY');
    const eventHtml = hasEvent ? `<span class="event-tag">🎪 Active Event</span>` : `<span style="color: #64748B;">None</span>`;

    tr.innerHTML = `
      <td>
        <span class="zone-id-tag">${zone.zone_id}</span>
        <span class="zone-title">${zone.zone_name}</span>
      </td>
      <td>
        <div class="demand-bar-container">
          <span class="demand-num">${zone.predicted_requests}</span>
          <div class="demand-bar">
            <div class="demand-bar-fill ${fillClass}" style="width: ${fillPercent}%"></div>
          </div>
        </div>
      </td>
      <td>
        <span class="${badgeClass}">${demandLevel}</span>
      </td>
      <td>
        <strong>${zone.available_drivers}</strong> idle
      </td>
      <td>
        ${gapHtml}
      </td>
      <td>
        ${eventHtml}
      </td>
      <td>
        <button class="btn btn-secondary btn-sm" onclick="dispatchToZone('${zone.zone_id}', '${zone.zone_name}')">
          Target Zone
        </button>
      </td>
    `;
    zonesTableBody.appendChild(tr);
  });
}

// ============================================================================
// PERSONALIZED RECOMMENDATIONS (FOR ME)
// ============================================================================
async function loadPersonalRecommendations() {
  personalCardsContainer.innerHTML = '<div style="color: #94A3B8; padding: 20px;">Computing closest high-demand zones for you...</div>';

  try {
    const res = await fetch(`/api/recommendations/for-me?zone_id=${state.currentZone}`);
    if (!res.ok) throw new Error('Failed to compute personalized recommendations');
    const data = await res.json();
    state.personalRecommendations = data;

    personalCurrentZoneName.textContent = `${data.driver_current_zone.zone_id} (${data.driver_current_zone.zone_name})`;
    personalCountBadge.textContent = data.recommendations.length;

    renderPersonalCards(data.recommendations);
  } catch (err) {
    console.error('Error fetching personal recommendations:', err);
    personalCardsContainer.innerHTML = `<div style="color: #EF4444; padding: 20px;">Error: ${err.message}</div>`;
  }
}

function renderPersonalCards(recommendations) {
  personalCardsContainer.innerHTML = '';

  if (!recommendations || recommendations.length === 0) {
    personalCardsContainer.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: #94A3B8;">
        <h3>No Urgent Repositioning Needed</h3>
        <p style="margin-top: 8px;">Your current zone has sufficient driver coverage. Stay online to receive passenger trip dispatches!</p>
      </div>
    `;
    return;
  }

  recommendations.forEach((item, index) => {
    const card = document.createElement('div');
    card.className = `rec-card ${index === 0 ? 'top-rank' : ''}`;

    const reasonPills = item.reason_codes
      .map((r) => `<span class="reason-pill">${r.replace(/_/g, ' ')}</span>`)
      .join('');

    card.innerHTML = `
      <div>
        <div class="rec-card-top">
          <div>
            <span class="rec-zone-id">${item.zone_id}</span>
            <h3 class="rec-zone-title">${item.zone_name}</h3>
          </div>
          <span class="rec-badge">${item.badge}</span>
        </div>

        <div class="rec-stats-row">
          <div class="rec-stat-col">
            <span class="rec-stat-num" style="color: #60A5FA;">⏱️ ${item.travel_time_min}m</span>
            <span class="rec-stat-label">Travel (${item.distance_km} km)</span>
          </div>
          <div class="rec-stat-col">
            <span class="rec-stat-num" style="color: #F87171;">+${item.supply_gap}</span>
            <span class="rec-stat-label">Driver Gap</span>
          </div>
          <div class="rec-stat-col">
            <span class="rec-stat-num" style="color: #34D399;">${item.predicted_requests}</span>
            <span class="rec-stat-label">Forecast Demand</span>
          </div>
        </div>

        <div class="rec-reasons">
          ${reasonPills}
        </div>
      </div>

      <button class="btn btn-reposition" onclick="acceptReposition('${item.zone_id}', '${item.zone_name}', ${item.travel_time_min})">
        Accept Reposition & Navigate 🚀
      </button>
    `;
    personalCardsContainer.appendChild(card);
  });
}

// ============================================================================
// ACTIONS & NAVIGATION
// ============================================================================
function switchTab(tabName) {
  if (tabName === 'overall') {
    tabOverallBtn.classList.add('active');
    tabPersonalBtn.classList.remove('active');
    viewOverall.classList.remove('hidden');
    viewPersonal.classList.add('hidden');
  } else {
    tabPersonalBtn.classList.add('active');
    tabOverallBtn.classList.remove('active');
    viewPersonal.classList.remove('hidden');
    viewOverall.classList.add('hidden');
    loadPersonalRecommendations();
  }
}

window.acceptReposition = function (zoneId, zoneName, travelTime) {
  state.activeNavigation = { zoneId, zoneName, travelTime };
  navTitle.textContent = `Repositioning Accepted: ${zoneName} (${zoneId})`;
  navDesc.textContent = `Route activated • Estimated driving time: ${travelTime} mins • Surge bonus active`;
  navAlert.classList.remove('hidden');

  driverStatusDisplay.textContent = `En Route to ${zoneId}`;
  driverStatusDisplay.parentElement.style.background = 'var(--warning-bg)';
  driverStatusDisplay.parentElement.style.color = '#FBBF24';
  driverStatusDisplay.parentElement.style.borderColor = 'rgba(245, 158, 11, 0.4)';

  window.scrollTo({ top: 0, behavior: 'smooth' });
};

window.dispatchToZone = function (zoneId, zoneName) {
  // Quickly switch to personalized tab with this zone or prompt navigate
  state.activeNavigation = { zoneId, zoneName, travelTime: 12 };
  navTitle.textContent = `Targeting Zone: ${zoneName} (${zoneId})`;
  navDesc.textContent = `Driver reposition dispatch initiated. Head towards ${zoneName}.`;
  navAlert.classList.remove('hidden');
  window.scrollTo({ top: 0, behavior: 'smooth' });
};
