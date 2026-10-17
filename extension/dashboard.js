/**
 * ExamRadar India - Dashboard Controller
 * Robust, CSP-compliant controller for full extension dashboard.
 */

const api = new ExamRadarAPI();

// State
let currentView = 'dashboard';
let currentNotifications = [];
let currentPage = 1;
let totalPages = 1;
let categoriesList = [];
let profileData = null;

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
  initTheme();
  initNav();
  initHeaderButtons();
  await loadCategories();
  await loadStats();

  const initialHash = window.location.hash ? window.location.hash.substring(1) : 'dashboard';
  handleRouting(initialHash);
});

// ===== Theme =====
function initTheme() {
  const saved = localStorage.getItem('examradar-theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('examradar-theme', next);
}

// ===== Navigation & Routing =====
function initNav() {
  const navButtons = document.querySelectorAll('#sideNav button');
  navButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const view = btn.dataset.view;
      window.location.hash = view;
    });
  });

  window.addEventListener('hashchange', () => {
    const hash = window.location.hash.substring(1);
    handleRouting(hash || 'dashboard');
  });
}

function handleRouting(hash) {
  if (hash.startsWith('notification/')) {
    const notifId = hash.split('/')[1];
    navigateTo('all');
    if (notifId) {
      setTimeout(() => openDetailModal(notifId), 200);
    }
    return;
  }
  navigateTo(hash);
}

function initHeaderButtons() {
  document.getElementById('refreshBtn')?.addEventListener('click', async () => {
    await loadStats();
    navigateTo(currentView);
  });
  document.getElementById('themeBtn')?.addEventListener('click', toggleTheme);
}

function navigateTo(view) {
  currentView = view || 'dashboard';

  // Update nav button active classes
  document.querySelectorAll('#sideNav button').forEach(btn => {
    if (btn.dataset.view === currentView) {
      btn.className = 'btn btn-sm btn-primary';
    } else {
      btn.className = 'btn btn-sm btn-ghost';
    }
  });

  const contentArea = document.getElementById('contentArea');
  contentArea.innerHTML = '<div class="loading-skeleton skeleton-card" style="margin:24px;"><div class="skeleton-line w-50"></div><div class="skeleton-line w-75"></div></div>';

  switch (currentView) {
    case 'dashboard':
      renderDashboardView();
      break;
    case 'all':
      renderAllView();
      break;
    case 'saved':
      renderSavedView();
      break;
    case 'profile':
      renderProfileView();
      break;
    case 'sources':
      renderSourcesView();
      break;
    case 'settings':
      renderSettingsView();
      break;
    default:
      renderDashboardView();
  }
}

// ===== Common Data =====
async function loadCategories() {
  try {
    const data = await api.getCategories();
    if (data && Array.isArray(data.categories)) {
      categoriesList = data.categories;
    } else if (Array.isArray(data)) {
      categoriesList = data;
    } else {
      categoriesList = [];
    }
  } catch (err) {
    console.error('Error loading categories:', err);
    categoriesList = [];
  }
}

async function loadStats() {
  try {
    const data = await api.getDashboard();
    document.getElementById('statOpen').textContent = data.total_open ?? 0;
    document.getElementById('statNew').textContent = data.newly_discovered ?? 0;
    document.getElementById('statMatch').textContent = data.matching_profile ?? 0;
    document.getElementById('statClosing').textContent = data.closing_soon ?? 0;

    if (data.last_updated) {
      const d = new Date(data.last_updated);
      document.getElementById('lastUpdated').textContent = `Last updated: ${formatDateTime(d)}`;
    } else {
      document.getElementById('lastUpdated').textContent = 'Live updates connected';
    }
  } catch (err) {
    document.getElementById('lastUpdated').textContent = 'Backend offline';
  }
}

// ===== VIEWS =====

// 1. DASHBOARD VIEW
async function renderDashboardView() {
  const contentArea = document.getElementById('contentArea');
  try {
    const [recData, closingData] = await Promise.all([
      api.getNotifications({ page: 1, page_size: 6, sort_by: 'recommended' }).catch(() => ({ items: [] })),
      api.getClosingSoon(10).catch(() => ({ items: [] }))
    ]);

    let html = `
      <div class="fade-in" style="padding: 16px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
          <h2 class="section-title" style="padding:0;">Recommended For You</h2>
          <button class="btn btn-sm btn-outline" id="viewAllBtn">Browse All Notifications &rarr;</button>
        </div>
        <div class="notification-list" style="padding:0; margin-bottom:24px;">
    `;

    const recItems = ((recData && Array.isArray(recData.items)) ? recData.items : (Array.isArray(recData) ? recData : [])).filter(item => !item.is_synthetic);
    if (recItems.length === 0) {
      html += `
        <div class="empty-state">
          <h3>No verified notifications found yet</h3>
          <p>Complete your qualifications and age in your Profile to match verified government vacancies, or monitor portal health in Sources.</p>
          <button class="btn btn-sm btn-primary" id="dashViewSourcesBtn" style="margin-top:10px;">View Source Monitoring Status</button>
        </div>
      `;
    } else {
      html += recItems.map(item => renderNotificationCard(item)).join('');
    }

    html += `
        </div>
        <h2 class="section-title" style="padding:0; margin-bottom:16px;">Closing Soon (Next 10 Days)</h2>
        <div class="notification-list" style="padding:0;">
    `;

    const closingItems = ((closingData && Array.isArray(closingData.items)) ? closingData.items : (Array.isArray(closingData) ? closingData : [])).filter(item => !item.is_synthetic);
    if (closingItems.length === 0) {
      html += `
        <div class="empty-state" style="padding:16px;">
          <p>No applications closing within the next 10 days.</p>
        </div>
      `;
    } else {
      html += closingItems.map(item => renderNotificationCard(item)).join('');
    }

    html += `</div></div>`;
    contentArea.innerHTML = html;

    document.getElementById('viewAllBtn')?.addEventListener('click', () => {
      window.location.hash = 'all';
    });
    document.getElementById('dashViewSourcesBtn')?.addEventListener('click', () => {
      window.location.hash = 'sources';
    });
    attachCardListeners(contentArea);
  } catch (err) {
    renderErrorState(contentArea, err.message);
  }
}

// 2. ALL NOTIFICATIONS VIEW
async function renderAllView() {
  const contentArea = document.getElementById('contentArea');
  const catOptions = categoriesList.map(c => {
    const val = c.value || c.slug || '';
    const label = c.label || c.name || val;
    return `<option value="${escapeHtml(val)}">${escapeHtml(label)}</option>`;
  }).join('');

  contentArea.innerHTML = `
    <div class="fade-in" style="padding: 16px;">
      <!-- Filters Bar -->
      <div class="search-filter-bar" style="margin-bottom: 16px; background:var(--bg-secondary); padding:16px; border-radius:var(--border-radius); border:1px solid var(--border-color);">
        <div style="display:flex; gap:8px; margin-bottom:12px; flex-wrap:wrap;">
          <input type="text" id="allSearchInput" class="form-input" style="flex:1; min-width:200px;" placeholder="Search exams, posts, organizations (e.g. UPSC, SSC CGL)...">
          <select id="allCatFilter" class="form-select" style="min-width:140px;">
            <option value="">All Categories</option>
            ${catOptions}
          </select>
          <select id="allSortFilter" class="form-select" style="min-width:140px;">
            <option value="newest">Newest Published</option>
            <option value="recommended">Best Match</option>
            <option value="deadline">Application Deadline</option>
            <option value="vacancies">Most Vacancies</option>
          </select>
        </div>
        <div style="display:flex; gap:12px; font-size:var(--font-size-sm); color:var(--text-secondary); align-items:center;">
          <label style="display:flex; align-items:center; gap:6px; cursor:pointer;">
            <input type="checkbox" id="onlyEligibleFilter"> Matching my profile only
          </label>
        </div>
      </div>

      <!-- Notification list container -->
      <div id="allListContainer">
        <div class="loading-skeleton skeleton-card"><div class="skeleton-line w-50"></div></div>
      </div>

      <!-- Pagination -->
      <div class="pagination" id="allPagination" style="display:none;">
        <button class="btn btn-sm btn-outline" id="allPrevBtn">&larr; Previous</button>
        <span class="page-info" id="allPageInfo">Page 1 of 1</span>
        <button class="btn btn-sm btn-outline" id="allNextBtn">Next &rarr;</button>
      </div>
    </div>
  `;

  // Attach search/filter events
  const searchInput = document.getElementById('allSearchInput');
  const catFilter = document.getElementById('allCatFilter');
  const sortFilter = document.getElementById('allSortFilter');
  const eligibleFilter = document.getElementById('onlyEligibleFilter');

  const reload = debounce(() => {
    currentPage = 1;
    fetchAllNotifications();
  }, 350);

  searchInput?.addEventListener('input', reload);
  catFilter?.addEventListener('change', () => { currentPage = 1; fetchAllNotifications(); });
  sortFilter?.addEventListener('change', () => { currentPage = 1; fetchAllNotifications(); });
  eligibleFilter?.addEventListener('change', () => { currentPage = 1; fetchAllNotifications(); });

  document.getElementById('allPrevBtn')?.addEventListener('click', () => {
    if (currentPage > 1) { currentPage--; fetchAllNotifications(); }
  });
  document.getElementById('allNextBtn')?.addEventListener('click', () => {
    if (currentPage < totalPages) { currentPage++; fetchAllNotifications(); }
  });

  currentPage = 1;
  await fetchAllNotifications();
}

async function fetchAllNotifications() {
  const container = document.getElementById('allListContainer');
  if (!container) return;

  const search = document.getElementById('allSearchInput')?.value || '';
  const category = document.getElementById('allCatFilter')?.value || '';
  const sort = document.getElementById('allSortFilter')?.value || 'newest';
  const onlyEligible = document.getElementById('onlyEligibleFilter')?.checked;

  container.innerHTML = '<div class="loading-skeleton skeleton-card"><div class="skeleton-line w-75"></div><div class="skeleton-line w-50"></div></div>';

  try {
    const params = {
      page: currentPage,
      page_size: 10,
      search: search || undefined,
      category: category || undefined,
      sort_by: sort,
      eligibility: onlyEligible ? 'likely_eligible' : undefined,
    };

    currentNotifications = ((res && Array.isArray(res.items)) ? res.items : []).filter(item => !item.is_synthetic);
    const totalCount = res.total || currentNotifications.length;
    totalPages = Math.max(1, Math.ceil(totalCount / (res.page_size || 10)));

    if (currentNotifications.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <h3>No verified notifications found yet</h3>
          <p>Try adjusting your search filters or check Source Monitoring to verify portal connectivity.</p>
          <button class="btn btn-primary btn-sm" id="emptyViewSourcesBtn" style="margin-top:12px;">View Source Monitoring Status</button>
        </div>
      `;
      document.getElementById('emptyViewSourcesBtn')?.addEventListener('click', () => {
        window.location.hash = 'sources';
      });
      const pag = document.getElementById('allPagination');
      if (pag) pag.style.display = 'none';
      return;
    }

    container.innerHTML = `
      <div class="notification-list" style="padding:0;">
        ${currentNotifications.map(item => renderNotificationCard(item)).join('')}
      </div>
    `;

    // Pagination update
    const pagination = document.getElementById('allPagination');
    if (pagination) {
      pagination.style.display = totalPages > 1 ? 'flex' : 'none';
      const pageInfo = document.getElementById('allPageInfo');
      if (pageInfo) pageInfo.textContent = `Page ${currentPage} of ${totalPages} (${totalCount} total)`;
      const prevBtn = document.getElementById('allPrevBtn');
      if (prevBtn) prevBtn.disabled = currentPage <= 1;
      const nextBtn = document.getElementById('allNextBtn');
      if (nextBtn) nextBtn.disabled = currentPage >= totalPages;
    }

    attachCardListeners(container);
  } catch (err) {
    container.innerHTML = `<div class="error-state"><p>${escapeHtml(err.message)}</p></div>`;
  }
}

// 3. SAVED NOTIFICATIONS VIEW
async function renderSavedView() {
  const contentArea = document.getElementById('contentArea');
  contentArea.innerHTML = '<div class="loading-skeleton skeleton-card"><div class="skeleton-line w-50"></div></div>';

  try {
    const savedItems = await api.getSaved();
    if (!savedItems || savedItems.length === 0) {
      contentArea.innerHTML = `
        <div class="fade-in empty-state" style="padding:48px;">
          <h3>No saved notifications</h3>
          <p>Click the bookmark icon on any exam notification card to save it for easy tracking.</p>
        </div>
      `;
      return;
    }

    let html = `
      <div class="fade-in" style="padding:16px;">
        <h2 class="section-title" style="padding:0; margin-bottom:16px;">Saved Exams & Applications (${savedItems.length})</h2>
        <div class="notification-list" style="padding:0;">
    `;

    savedItems.forEach(entry => {
      const item = entry.notification || {};
      const notifId = entry.notification_id || item.id;
      const isApplied = entry.is_applied;
      const org = item.organization_short_name || item.organization_name || 'Govt';
      const title = item.title || `Notification #${notifId}`;

      html += `
        <div class="notification-card" data-id="${notifId}">
          <div class="card-header">
            <div>
              <span class="badge badge-org">${escapeHtml(org)}</span>
              ${item.application_status ? `<span class="badge badge-status">${escapeHtml(item.application_status)}</span>` : ''}
              ${isApplied ? '<span class="badge badge-match" style="background:var(--color-success); color:white;">Applied &#10003;</span>' : ''}
            </div>
            <button class="btn btn-sm ${isApplied ? 'btn-outline' : 'btn-primary'} mark-applied-btn" data-id="${notifId}">
              ${isApplied ? 'Mark Not Applied' : 'Mark as Applied'}
            </button>
          </div>
          <h3 class="card-title">${escapeHtml(title)}</h3>
          <div class="card-meta">
            ${item.total_vacancies ? `<span>Vacancies: <strong>${item.total_vacancies.toLocaleString()}</strong></span>` : ''}
            ${item.application_end_date ? `<span>Deadline: <strong>${formatDate(item.application_end_date)}</strong></span>` : ''}
          </div>
          <div class="card-actions">
            <button class="btn btn-sm btn-outline view-details-btn" data-id="${notifId}">View Details</button>
            ${item.official_notification_url ? `<a href="${item.official_notification_url}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-ghost">Official Portal &nearr;</a>` : ''}
            <button class="btn btn-sm btn-ghost unsave-btn" data-id="${notifId}" style="color:var(--color-danger); margin-left:auto;">Remove</button>
          </div>
        </div>
      `;
    });

    html += `</div></div>`;
    contentArea.innerHTML = html;

    // Attach listeners
    contentArea.querySelectorAll('.view-details-btn').forEach(btn => {
      btn.addEventListener('click', () => openDetailModal(btn.dataset.id));
    });

    contentArea.querySelectorAll('.unsave-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        try {
          await api.unsaveNotification(btn.dataset.id);
          renderSavedView();
        } catch (err) {
          alert('Could not remove: ' + err.message);
        }
      });
    });

    contentArea.querySelectorAll('.mark-applied-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        try {
          await api.markApplied(btn.dataset.id);
          renderSavedView();
        } catch (err) {
          alert('Error updating status: ' + err.message);
        }
      });
    });
  } catch (err) {
    renderErrorState(contentArea, err.message);
  }
}

// 4. PROFILE VIEW
async function renderProfileView() {
  const contentArea = document.getElementById('contentArea');
  contentArea.innerHTML = '<div class="loading-skeleton skeleton-card"><div class="skeleton-line w-50"></div></div>';

  try {
    profileData = await api.getProfile().catch(() => null);
  } catch (err) {
    profileData = null;
  }

  const p = profileData || {};
  const qual = (p.qualifications && p.qualifications[0]) || {};

  contentArea.innerHTML = `
    <div class="fade-in profile-container">
      <h2 class="section-title" style="padding:0; margin-bottom:8px;">Candidate Profile & Eligibility Matcher</h2>
      <p style="color:var(--text-secondary); font-size:var(--font-size-sm); margin-bottom:20px;">
        Provide your qualifications, category, and preferences. The system will automatically calculate your age, category relaxation, and highlight notifications you qualify for.
      </p>

      <form id="profileForm" style="display:flex; flex-direction:column; gap:16px;">
        <div style="background:var(--bg-secondary); padding:16px; border-radius:var(--border-radius); border:1px solid var(--border-color);">
          <h3 style="font-size:14px; font-weight:600; margin-bottom:12px;">Basic Information</h3>
          <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:12px;">
            <div>
              <label class="form-label">Date of Birth</label>
              <input type="date" id="profDob" class="form-input" value="${p.date_of_birth ? p.date_of_birth.substring(0, 10) : ''}">
            </div>
            <div>
              <label class="form-label">Reservation Category</label>
              <select id="profCategory" class="form-select">
                <option value="GEN" ${p.reservation_category === 'GEN' ? 'selected' : ''}>General (UR)</option>
                <option value="EWS" ${p.reservation_category === 'EWS' ? 'selected' : ''}>EWS</option>
                <option value="OBC" ${p.reservation_category === 'OBC' ? 'selected' : ''}>OBC (Non-Creamy)</option>
                <option value="SC" ${p.reservation_category === 'SC' ? 'selected' : ''}>SC</option>
                <option value="ST" ${p.reservation_category === 'ST' ? 'selected' : ''}>ST</option>
                <option value="PWD" ${p.is_pwbd ? 'selected' : ''}>PwBD</option>
                <option value="EX_SERVICEMAN" ${p.is_ex_serviceman ? 'selected' : ''}>Ex-Servicemen</option>
              </select>
            </div>
            <div>
              <label class="form-label">Gender</label>
              <select id="profGender" class="form-select">
                <option value="">Select Gender</option>
                <option value="Male" ${p.gender === 'Male' ? 'selected' : ''}>Male</option>
                <option value="Female" ${p.gender === 'Female' ? 'selected' : ''}>Female</option>
                <option value="Other" ${p.gender === 'Other' ? 'selected' : ''}>Other</option>
              </select>
            </div>
            <div>
              <label class="form-label">State / UT Domicile</label>
              <input type="text" id="profState" class="form-input" value="${escapeHtml(p.domicile_state || p.state_of_residence || '')}" placeholder="e.g. West Bengal, Maharashtra">
            </div>
          </div>
        </div>

        <div style="background:var(--bg-secondary); padding:16px; border-radius:var(--border-radius); border:1px solid var(--border-color);">
          <h3 style="font-size:14px; font-weight:600; margin-bottom:12px;">Highest Educational Qualification</h3>
          <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:12px;">
            <div>
              <label class="form-label">Qualification Level</label>
              <select id="profQualLevel" class="form-select">
                <option value="10th" ${qual.level === '10th' ? 'selected' : ''}>10th / Matriculation</option>
                <option value="12th" ${qual.level === '12th' ? 'selected' : ''}>12th / Intermediate</option>
                <option value="Diploma" ${qual.level === 'Diploma' ? 'selected' : ''}>Diploma</option>
                <option value="Graduate" ${qual.level === 'Graduate' || !qual.level ? 'selected' : ''}>Graduate (B.A., B.Sc., B.Tech, etc.)</option>
                <option value="PostGraduate" ${qual.level === 'PostGraduate' ? 'selected' : ''}>Post Graduate (M.A., M.Sc., M.Tech, etc.)</option>
                <option value="PhD" ${qual.level === 'PhD' ? 'selected' : ''}>Ph.D. / Doctorate</option>
              </select>
            </div>
            <div>
              <label class="form-label">Degree / Course Name</label>
              <input type="text" id="profDegree" class="form-input" value="${escapeHtml(qual.degree_name || '')}" placeholder="e.g. B.Tech / B.Sc / B.Com">
            </div>
            <div>
              <label class="form-label">Specialization / Discipline</label>
              <input type="text" id="profField" class="form-input" value="${escapeHtml(qual.specialization || '')}" placeholder="e.g. Computer Science / Economics">
            </div>
            <div>
              <label class="form-label">Percentage / CGPA</label>
              <input type="text" id="profPercentage" class="form-input" value="${qual.percentage || ''}" placeholder="e.g. 75.5">
            </div>
          </div>
        </div>

        <div style="display:flex; gap:12px; justify-content:flex-end;">
          <button type="submit" class="btn btn-primary" id="saveProfileBtn">Save Profile & Recalculate</button>
        </div>
      </form>
    </div>
  `;

  document.getElementById('profileForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const saveBtn = document.getElementById('saveProfileBtn');
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    const dobVal = document.getElementById('profDob').value;
    const catVal = document.getElementById('profCategory').value;
    const stateVal = document.getElementById('profState').value;

    const updatePayload = {
      date_of_birth: dobVal || null,
      domicile_state: stateVal || null,
      state_of_residence: stateVal || null,
      nationality: 'Indian',
      gender: document.getElementById('profGender').value || null,
      reservation_category: catVal === 'PWD' || catVal === 'EX_SERVICEMAN' ? 'GEN' : catVal,
      is_pwbd: catVal === 'PWD',
      is_ex_serviceman: catVal === 'EX_SERVICEMAN',
      profile_matching_enabled: true,
      qualifications: [{
        level: document.getElementById('profQualLevel').value,
        degree_name: document.getElementById('profDegree').value || null,
        specialization: document.getElementById('profField').value || null,
        percentage: document.getElementById('profPercentage').value || null,
        graduation_status: 'completed',
        is_highest: true
      }],
      career_preferences: []
    };

    try {
      await api.updateProfile(updatePayload);
      alert('Profile updated successfully! Eligibility matches recalculated.');
      await loadStats();
      renderProfileView();
    } catch (err) {
      alert('Failed to update profile: ' + err.message);
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save Profile & Recalculate';
    }
  });
}

// 5. SOURCES VIEW
async function renderSourcesView() {
  const contentArea = document.getElementById('contentArea');
  contentArea.innerHTML = '<div class="loading-skeleton skeleton-card"><div class="skeleton-line w-50"></div></div>';

  try {
    const [sources, statusData] = await Promise.all([
      api.getSources().catch(() => []),
      api.getSourceStatus().catch(() => ({ total_sources: 0, enabled_sources: 0, sources_with_errors: 0 }))
    ]);

    const total = statusData.total_sources || sources.length;
    const enabled = statusData.enabled_sources || sources.filter(s => s.is_enabled).length;
    const errors = statusData.sources_with_errors || sources.filter(s => (s.error_count || 0) > 0).length;
    const healthy = enabled - errors;

    let html = `
      <div class="fade-in sources-container">
        <!-- Coverage Disclaimer -->
        <div style="background:var(--color-info-bg); border-left:4px solid var(--color-info); padding:12px 16px; margin-bottom:20px; border-radius:var(--border-radius-sm); font-size:12px; line-height:1.5; color:var(--text-secondary);">
          <strong>Coverage & Verification Notice:</strong> ExamRadar India tracks and verifies notifications from selected authoritative central and state government recruitment commissions. It does <em>not</em> claim full coverage of all public sector enterprises, local municipal bodies, or autonomous academic institutions across India.
        </div>

        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:12px;">
          <div>
            <h2 class="section-title" style="padding:0;">Official Recruitment Commission Sources</h2>
            <p style="color:var(--text-secondary); font-size:var(--font-size-sm);">
              Scheduled backend monitoring authoritative status for registered portals.
            </p>
          </div>
          <button class="btn btn-primary" id="runDiscoveryBtn">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:6px;">
              <path d="M23 4v6h-6M1 20v-6h6"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>
            </svg>
            Trigger Background Discovery Now
          </button>
        </div>

        <!-- Monitoring Status Cards -->
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(140px, 1fr)); gap:12px; margin-bottom:20px;">
          <div style="background:var(--bg-secondary); padding:12px 16px; border-radius:var(--border-radius); border:1px solid var(--border-color);">
            <div style="font-size:11px; color:var(--text-tertiary); text-transform:uppercase;">Configured Portals</div>
            <div style="font-size:20px; font-weight:700; color:var(--text-primary);">${total}</div>
          </div>
          <div style="background:var(--bg-secondary); padding:12px 16px; border-radius:var(--border-radius); border:1px solid var(--border-color);">
            <div style="font-size:11px; color:var(--text-tertiary); text-transform:uppercase;">Active Monitored</div>
            <div style="font-size:20px; font-weight:700; color:var(--color-primary);">${enabled}</div>
          </div>
          <div style="background:var(--bg-secondary); padding:12px 16px; border-radius:var(--border-radius); border:1px solid var(--border-color);">
            <div style="font-size:11px; color:var(--text-tertiary); text-transform:uppercase;">Healthy Checks</div>
            <div style="font-size:20px; font-weight:700; color:var(--color-success);">${healthy}</div>
          </div>
          <div style="background:var(--bg-secondary); padding:12px 16px; border-radius:var(--border-radius); border:1px solid var(--border-color);">
            <div style="font-size:11px; color:var(--text-tertiary); text-transform:uppercase;">Sources With Errors</div>
            <div style="font-size:20px; font-weight:700; color:${errors > 0 ? 'var(--color-danger)' : 'var(--text-primary)'};">${errors}</div>
          </div>
        </div>

        <table class="sources-table">
          <thead>
            <tr>
              <th>Commission / Agency</th>
              <th>Category</th>
              <th>Official Portal</th>
              <th>Status</th>
              <th>Notifications Found</th>
              <th>Health / Errors</th>
              <th>Last Checked (IST)</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
    `;

    if (sources.length === 0) {
      html += `<tr><td colspan="8" style="text-align:center; padding:24px;">No sources configured</td></tr>`;
    } else {
      sources.forEach(s => {
        const orgName = s.organization_name || s.name || 'Portal';
        const cat = s.category || 'Recruitment';
        const isActive = s.is_enabled;
        const hasErrors = (s.error_count || 0) > 0;
        const count = s.notifications_count || 0;

        html += `
          <tr>
            <td>
              <strong>${escapeHtml(s.name)}</strong>
              ${s.organization_name ? `<div style="font-size:11px; color:var(--text-secondary);">${escapeHtml(orgName)}</div>` : ''}
            </td>
            <td><span class="badge badge-org">${escapeHtml(cat)}</span></td>
            <td><a href="${s.base_url}" target="_blank" rel="noopener noreferrer" style="color:var(--color-primary); word-break:break-all;">${escapeHtml(s.base_url)}</a></td>
            <td>
              <span class="badge ${isActive ? 'badge-match' : 'badge-status'}" style="${isActive ? 'background:var(--color-success-bg); color:var(--color-success);' : ''}">
                ${isActive ? 'Active' : 'Paused'}
              </span>
            </td>
            <td><strong>${count}</strong> verified</td>
            <td>
              ${hasErrors
                ? `<span class="badge badge-closing" title="${escapeHtml(s.last_error || 'Error during fetch')}">${s.error_count} error(s)</span>
                   <div style="font-size:10px; color:var(--color-danger); max-width:180px; word-break:break-word; margin-top:2px;">${escapeHtml(s.last_error ? s.last_error.substring(0, 60) + '...' : '')}</div>`
                : '<span class="badge badge-match" style="background:var(--color-success-bg); color:var(--color-success);">✓ OK</span>'}
            </td>
            <td>${s.last_successful_check ? formatDateTime(new Date(s.last_successful_check)) : 'Scheduled'}</td>
            <td>
              <button class="btn btn-sm btn-outline test-source-btn" data-source-id="${s.id}" style="padding:4px 8px; font-size:11px;">
                Test Run
              </button>
            </td>
          </tr>
        `;
      });
    }

    html += `
          </tbody>
        </table>
      </div>
    `;

    contentArea.innerHTML = html;

    document.getElementById('runDiscoveryBtn')?.addEventListener('click', async (e) => {
      const btn = e.currentTarget;
      btn.disabled = true;
      btn.textContent = 'Discovering...';
      try {
        const res = await api.triggerDiscovery();
        alert(res.message || 'Discovery run initiated successfully!');
        await loadStats();
        renderSourcesView();
      } catch (err) {
        alert('Discovery error: ' + err.message);
        btn.disabled = false;
        btn.textContent = 'Trigger Background Discovery Now';
      }
    });

    contentArea.querySelectorAll('.test-source-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const sourceId = btn.dataset.sourceId;
        btn.disabled = true;
        btn.textContent = 'Checking...';
        try {
          const res = await api.triggerDiscovery(sourceId);
          alert(res.message || 'Discovery completed for source!');
          await loadStats();
          renderSourcesView();
        } catch (err) {
          alert('Discovery error: ' + err.message);
          btn.disabled = false;
          btn.textContent = 'Test Run';
        }
      });
    });
  } catch (err) {
    renderErrorState(contentArea, err.message);
  }
}

// 6. SETTINGS VIEW
function renderSettingsView() {
  const contentArea = document.getElementById('contentArea');
  const savedUrl = localStorage.getItem('examradar-api-url') || 'http://localhost:8000';

  contentArea.innerHTML = `
    <div class="fade-in profile-container">
      <h2 class="section-title" style="padding:0; margin-bottom:16px;">Extension Settings</h2>
      <div style="background:var(--bg-secondary); padding:16px; border-radius:var(--border-radius); border:1px solid var(--border-color); display:flex; flex-direction:column; gap:16px;">
        <div>
          <label class="form-label">Backend API URL</label>
          <input type="text" id="settingApiUrl" class="form-input" value="${escapeHtml(savedUrl)}" placeholder="http://localhost:8000">
          <small style="color:var(--text-tertiary); display:block; margin-top:4px;">ExamRadar India backend service endpoint.</small>
        </div>

        <div>
          <label class="form-label">Appearance Theme</label>
          <select id="settingThemeSelect" class="form-select">
            <option value="light" ${document.documentElement.getAttribute('data-theme') !== 'dark' ? 'selected' : ''}>Light Theme</option>
            <option value="dark" ${document.documentElement.getAttribute('data-theme') === 'dark' ? 'selected' : ''}>Dark Theme</option>
          </select>
        </div>

        <div style="display:flex; gap:12px; margin-top:8px;">
          <button class="btn btn-primary" id="saveSettingsBtn">Save Settings</button>
          <button class="btn btn-outline" id="testApiBtn">Test Backend Connection</button>
        </div>
      </div>
    </div>
  `;

  document.getElementById('saveSettingsBtn')?.addEventListener('click', async () => {
    const val = document.getElementById('settingApiUrl').value.trim() || 'http://localhost:8000';
    localStorage.setItem('examradar-api-url', val);
    if (typeof chrome !== 'undefined' && chrome.storage) {
      await chrome.storage.local.set({ apiBaseUrl: val });
    }
    api.baseUrl = val;

    const theme = document.getElementById('settingThemeSelect').value;
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('examradar-theme', theme);

    alert('Settings saved!');
    loadStats();
  });

  document.getElementById('testApiBtn')?.addEventListener('click', async () => {
    const btn = document.getElementById('testApiBtn');
    btn.disabled = true;
    btn.textContent = 'Testing...';
    try {
      const res = await api.health();
      alert(`Connected! Service status: ${res.status || 'OK'}`);
    } catch (err) {
      alert(`Connection failed: ${err.message}`);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Test Backend Connection';
    }
  });
}

// ===== NOTIFICATION CARD RENDERER =====
function renderNotificationCard(item) {
  const isEligible = item.eligibility_match === 'eligible' || item.is_eligible;
  const isClosing = item.application_status === 'closing_soon' || item.is_closing_soon;
  const orgCode = item.organization_short_name || item.organization_name || item.organization?.code || item.organization?.name || 'Govt';
  const vacancies = item.total_vacancies ? `${item.total_vacancies.toLocaleString()} vacancies` : '';
  const deadline = item.application_end_date ? `Closes ${formatDate(item.application_end_date)}` : '';
  const notifUrl = item.official_notification_url || item.official_source_url;
  const applyUrl = item.official_application_url || item.application_link;

  return `
    <div class="notification-card" data-id="${item.id}">
      <div class="card-header">
        <div>
          <span class="badge badge-org">${escapeHtml(orgCode)}</span>
          <span class="badge badge-status">${escapeHtml(formatStatus(item.application_status))}</span>
          ${isEligible ? '<span class="badge badge-match">&#10003; Eligible</span>' : ''}
          ${isClosing ? '<span class="badge badge-closing">&#9888; Closing Soon</span>' : ''}
        </div>
        <button class="btn-icon bookmark-btn" data-id="${item.id}" title="Save to bookmarks">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="${item.is_saved ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2">
            <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
          </svg>
        </button>
      </div>
      <h3 class="card-title">${escapeHtml(item.title)}</h3>
      <div class="card-meta">
        ${vacancies ? `<span>${vacancies}</span>` : ''}
        ${deadline ? `<span>${deadline}</span>` : ''}
        ${item.educational_qualification ? `<span>${escapeHtml(item.educational_qualification)}</span>` : ''}
      </div>
      <div class="card-actions">
        <button class="btn btn-sm btn-outline view-details-btn" data-id="${item.id}">View Details</button>
        ${notifUrl ? `<a href="${notifUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-ghost">Official Portal &nearr;</a>` : ''}
        ${applyUrl ? `<a href="${applyUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-primary" style="margin-left:auto;">Apply Online &rarr;</a>` : ''}
      </div>
    </div>
  `;
}

function attachCardListeners(parent) {
  parent.querySelectorAll('.view-details-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      openDetailModal(btn.dataset.id);
    });
  });

  parent.querySelectorAll('.bookmark-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const id = btn.dataset.id;
      try {
        await api.saveNotification(id);
        btn.style.color = 'var(--color-primary)';
        btn.querySelector('svg')?.setAttribute('fill', 'currentColor');
        alert('Saved to bookmarks!');
      } catch (err) {
        alert('Could not save: ' + err.message);
      }
    });
  });
}

// ===== DETAIL MODAL =====
async function openDetailModal(id) {
  let modal = document.getElementById('detailModal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'detailModal';
    modal.style.cssText = `
      position:fixed; top:0; left:0; width:100vw; height:100vh;
      background:rgba(0,0,0,0.6); display:flex; justify-content:center;
      align-items:center; z-index:9999; padding:16px;
    `;
    document.body.appendChild(modal);
  }

  modal.style.display = 'flex';
  modal.innerHTML = `
    <div style="background:var(--bg-primary); width:100%; max-width:680px; max-height:85vh; border-radius:var(--border-radius-lg); overflow-y:auto; padding:24px; position:relative; box-shadow:var(--shadow-lg);">
      <button id="closeModalBtn" style="position:absolute; top:16px; right:16px; background:none; border:none; font-size:24px; cursor:pointer; color:var(--text-secondary);">&times;</button>
      <div class="loading-skeleton skeleton-card"><div class="skeleton-line w-75"></div><div class="skeleton-line w-50"></div></div>
    </div>
  `;

  document.getElementById('closeModalBtn')?.addEventListener('click', () => { modal.style.display = 'none'; });
  modal.onclick = (e) => { if (e.target === modal) modal.style.display = 'none'; };

  try {
    const item = await api.getNotification(id);
    const org = item.organization_name || item.organization?.name || 'Official Recruitment';
    const qual = item.educational_qualification || 'As per official advertisement';
    const minAge = item.min_age != null ? item.min_age : 'N/A';
    const maxAge = item.max_age != null ? item.max_age : 'N/A';
    const vacancies = item.total_vacancies ? item.total_vacancies.toLocaleString() : 'Refer notification';
    const fee = item.application_fee != null ? `₹${item.application_fee}` : 'Refer notification';
    const notifUrl = item.official_notification_url || item.source_url;
    const applyUrl = item.official_application_url || item.application_link;

    const inner = modal.querySelector('div');
    inner.innerHTML = `
      <button id="closeModalBtn" style="position:absolute; top:16px; right:16px; background:none; border:none; font-size:24px; cursor:pointer; color:var(--text-secondary);">&times;</button>
      
      <div style="margin-bottom:16px;">
        <span class="badge badge-org">${escapeHtml(org)}</span>
        <span class="badge badge-status">${escapeHtml(formatStatus(item.application_status))}</span>
        ${item.eligibility_match === 'eligible' ? '<span class="badge badge-match">&#10003; Eligible for you</span>' : ''}
      </div>

      <h2 style="font-size:20px; font-weight:700; margin-bottom:12px; line-height:1.3;">${escapeHtml(item.title)}</h2>
      ${item.post_name ? `<p style="color:var(--text-secondary); font-size:14px; margin-bottom:16px;"><strong>Post:</strong> ${escapeHtml(item.post_name)}</p>` : ''}

      <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:12px; background:var(--bg-secondary); padding:16px; border-radius:var(--border-radius); margin-bottom:20px;">
        <div><small style="color:var(--text-tertiary);">Total Vacancies</small><div style="font-weight:600; font-size:15px;">${vacancies}</div></div>
        <div><small style="color:var(--text-tertiary);">Age Limit</small><div style="font-weight:600; font-size:15px;">${minAge} - ${maxAge} yrs</div></div>
        <div><small style="color:var(--text-tertiary);">Application Start</small><div style="font-weight:600; font-size:15px;">${formatDate(item.application_start_date)}</div></div>
        <div><small style="color:var(--text-tertiary);">Application End</small><div style="font-weight:600; font-size:15px; color:var(--color-danger);">${formatDate(item.application_end_date)}</div></div>
      </div>

      <div style="display:flex; flex-direction:column; gap:16px; font-size:13px; line-height:1.6; margin-bottom:24px;">
        <div>
          <h4 style="font-size:14px; font-weight:600; margin-bottom:4px;">Educational Eligibility</h4>
          <p style="color:var(--text-secondary);">${escapeHtml(qual)}</p>
        </div>

        ${item.eligibility_explanation ? `
        <div>
          <h4 style="font-size:14px; font-weight:600; margin-bottom:4px;">Eligibility Status</h4>
          <p style="color:var(--text-secondary);">${escapeHtml(item.eligibility_explanation)}</p>
        </div>` : ''}

        <div>
          <h4 style="font-size:14px; font-weight:600; margin-bottom:4px;">Application Fee</h4>
          <p style="color:var(--text-secondary);">${escapeHtml(fee)}</p>
        </div>

        ${item.salary_range ? `
        <div>
          <h4 style="font-size:14px; font-weight:600; margin-bottom:4px;">Pay Scale / Salary</h4>
          <p style="color:var(--text-secondary);">${escapeHtml(item.salary_range)}</p>
        </div>` : ''}
      </div>

      <div style="display:flex; gap:12px; flex-wrap:wrap; border-top:1px solid var(--border-color); padding-top:16px;">
        ${applyUrl ? `<a href="${applyUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-primary">Apply Online &rarr;</a>` : ''}
        ${notifUrl ? `<a href="${notifUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-outline">Official Notification Link</a>` : ''}
        <button class="btn btn-outline" id="modalSaveBtn">Bookmark Exam</button>
      </div>
    `;

    document.getElementById('closeModalBtn')?.addEventListener('click', () => { modal.style.display = 'none'; });
    document.getElementById('modalSaveBtn')?.addEventListener('click', async () => {
      try {
        await api.saveNotification(item.id);
        alert('Notification bookmarked!');
      } catch (err) {
        alert(err.message);
      }
    });
  } catch (err) {
    modal.querySelector('div').innerHTML = `
      <button id="closeModalBtn" style="position:absolute; top:16px; right:16px; background:none; border:none; font-size:24px; cursor:pointer; color:var(--text-secondary);">&times;</button>
      <p style="color:var(--color-danger); padding:20px;">Failed to load details: ${escapeHtml(err.message)}</p>
    `;
    document.getElementById('closeModalBtn')?.addEventListener('click', () => { modal.style.display = 'none'; });
  }
}

// ===== UTILS =====
function formatDate(d) {
  if (!d) return 'TBA';
  const date = new Date(d);
  if (isNaN(date)) return 'TBA';
  return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function formatDateTime(d) {
  if (!d) return '';
  return d.toLocaleDateString('en-IN', {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
  });
}

function formatStatus(status) {
  if (!status) return 'Open';
  return status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function debounce(fn, delay) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

function renderErrorState(container, msg) {
  container.innerHTML = `
    <div class="fade-in error-state">
      <h3>Error Loading Data</h3>
      <p style="margin-bottom:12px;">${escapeHtml(msg)}</p>
      <button class="btn btn-sm btn-primary retry-btn">Retry</button>
    </div>
  `;
  container.querySelector('.retry-btn')?.addEventListener('click', () => {
    navigateTo(currentView);
  });
}
