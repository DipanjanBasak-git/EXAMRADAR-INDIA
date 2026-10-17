/**
 * ExamRadar India - Popup Controller
 * Manages the popup dashboard, tabs, filters, and notification cards.
 */

const api = new ExamRadarAPI();
let currentTab = 'recommended';
let currentPage = 1;
let currentFilters = {};
let totalPages = 1;

// ===== Initialization =====
document.addEventListener('DOMContentLoaded', async () => {
  initTheme();
  initEventListeners();
  await loadCategories();
  await loadDashboard();
  await loadNotifications();
});

// ===== Theme =====
function initTheme() {
  const savedTheme = localStorage.getItem('examradar-theme') || 'light';
  document.documentElement.setAttribute('data-theme', savedTheme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('examradar-theme', next);
}

// ===== Event Listeners =====
function initEventListeners() {
  document.getElementById('refreshBtn').addEventListener('click', refresh);
  document.getElementById('themeBtn').addEventListener('click', toggleTheme);
  document.getElementById('dashboardBtn').addEventListener('click', () => {
    chrome.runtime.sendMessage({ action: 'openDashboard' });
  });
  document.getElementById('settingsBtn').addEventListener('click', () => {
    chrome.tabs.create({ url: 'dashboard.html#profile' });
  });
  document.getElementById('retryBtn')?.addEventListener('click', refresh);

  // Tabs
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      currentTab = tab.dataset.tab;
      currentPage = 1;
      loadNotifications();
    });
  });

  // Filters
  document.getElementById('searchInput').addEventListener('input', debounce(() => {
    currentPage = 1;
    loadNotifications();
  }, 400));

  document.getElementById('categoryFilter').addEventListener('change', () => {
    currentPage = 1;
    loadNotifications();
  });

  document.getElementById('sortFilter').addEventListener('change', () => {
    currentPage = 1;
    loadNotifications();
  });

  // Pagination
  document.getElementById('prevPage').addEventListener('click', () => {
    if (currentPage > 1) { currentPage--; loadNotifications(); }
  });
  document.getElementById('nextPage').addEventListener('click', () => {
    if (currentPage < totalPages) { currentPage++; loadNotifications(); }
  });
}

// ===== Data Loading =====
async function loadDashboard() {
  try {
    const data = await api.getDashboard();
    document.getElementById('statOpen').textContent = data.total_open || 0;
    document.getElementById('statNew').textContent = data.newly_discovered || 0;
    document.getElementById('statMatch').textContent = data.matching_profile || 0;
    document.getElementById('statClosing').textContent = data.closing_soon || 0;

    if (data.last_updated) {
      const d = new Date(data.last_updated);
      document.getElementById('lastUpdated').textContent =
        `Last updated: ${formatDateTime(d)}`;
    } else {
      document.getElementById('lastUpdated').textContent = 'No data yet';
    }

    document.getElementById('errorState').style.display = 'none';
    document.getElementById('mainContent').style.display = 'block';
  } catch (error) {
    showError(error.message);
  }
}

async function loadCategories() {
  try {
    const data = await api.getCategories();
    const select = document.getElementById('categoryFilter');
    data.categories.forEach(cat => {
      const option = document.createElement('option');
      option.value = cat.value;
      option.textContent = cat.label;
      select.appendChild(option);
    });
  } catch (e) {
    console.error('Failed to load categories:', e);
  }
}

async function loadNotifications() {
  const container = document.getElementById('notificationsList');
  showLoading(container);

  const params = {
    page: currentPage,
    page_size: 15,
    search: document.getElementById('searchInput').value || undefined,
    category: document.getElementById('categoryFilter').value || undefined,
    sort_by: document.getElementById('sortFilter').value || 'newest',
  };

  // Tab-specific params
  switch (currentTab) {
    case 'recommended':
      params.eligibility = 'likely_eligible';
      break;
    case 'new':
      params.sort_by = 'newest';
      break;
    case 'open':
      params.status = 'application_open';
      break;
    case 'closing':
      params.closing_within_days = 7;
      params.sort_by = 'deadline';
      break;
    case 'results':
      params.status = 'result_declared';
      break;
  }

  try {
    const data = await api.getNotifications(params);
    totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
    renderNotifications(container, data.items);
    updatePagination(data);
    document.getElementById('errorState').style.display = 'none';
    document.getElementById('mainContent').style.display = 'block';
  } catch (error) {
    showError(error.message);
  }
}

async function refresh() {
  const btn = document.getElementById('refreshBtn');
  btn.style.opacity = '0.5';
  btn.disabled = true;

  try {
    await chrome.runtime.sendMessage({ action: 'refresh' });
    await loadDashboard();
    await loadNotifications();
  } catch (e) {
    console.error('Refresh failed:', e);
  } finally {
    btn.style.opacity = '1';
    btn.disabled = false;
  }
}

// ===== Rendering =====
function renderNotifications(container, items) {
  // Production filter: Exclude any synthetic test fixtures from live extension display
  const verifiedItems = (items || []).filter(n => !n.is_synthetic);

  if (!verifiedItems || verifiedItems.length === 0) {
    container.innerHTML = `
      <div class="empty-state fade-in">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/>
          <rect x="9" y="3" width="6" height="4" rx="1"/>
          <path d="M9 14l2 2 4-4"/>
        </svg>
        <h3>No verified notifications found yet</h3>
        <p>${currentTab === 'recommended'
          ? 'Set up your qualifications and age in Profile to match verified government vacancies.'
          : 'No genuine notices matching this filter yet. You can monitor official portals and check discovery status directly.'}</p>
        <button id="viewSourceStatusBtn" class="btn btn-sm btn-primary" style="margin-top:12px;">View Source Monitoring Status</button>
      </div>`;

    document.getElementById('viewSourceStatusBtn')?.addEventListener('click', () => {
      chrome.tabs.create({ url: 'dashboard.html#sources' });
    });
    return;
  }

  container.innerHTML = verifiedItems.map(n => createNotificationCard(n)).join('');

  // Attach click handlers
  container.querySelectorAll('.notification-card').forEach(card => {
    card.addEventListener('click', () => {
      const id = card.dataset.id;
      chrome.tabs.create({ url: `dashboard.html#notification/${id}` });
    });
  });

  container.querySelectorAll('.card-link').forEach(link => {
    link.addEventListener('click', (e) => {
      e.stopPropagation();
      const url = link.dataset.url;
      if (url) chrome.tabs.create({ url });
    });
  });

  container.querySelectorAll('.save-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const id = btn.dataset.id;
      try {
        await api.saveNotification(id);
        btn.textContent = '★ Saved';
        btn.classList.add('btn-accent');
      } catch (err) {
        console.error(err);
      }
    });
  });
}

function createNotificationCard(n) {
  const statusBadge = getStatusBadge(n.application_status);
  const eligBadge = getEligibilityBadge(n.eligibility_match);
  const verifyBadge = getVerificationBadge(n.verification_status);
  const categoryLabel = getCategoryLabel(n.category);

  const startDate = n.application_start_date ? formatDate(n.application_start_date) : '';
  const endDate = n.application_end_date ? formatDate(n.application_end_date) : '';
  let dateDisplay = '';
  if (startDate && endDate) {
    dateDisplay = `${startDate} → ${endDate}`;
  } else if (endDate) {
    dateDisplay = `Deadline: ${endDate}`;
  } else if (startDate) {
    dateDisplay = `Starts: ${startDate}`;
  } else if (n.notification_date) {
    dateDisplay = `Notice Date: ${formatDate(n.notification_date)}`;
  } else if (n.first_discovered_at) {
    dateDisplay = `Discovered: ${formatDate(n.first_discovered_at)}`;
  }

  const vacancies = n.total_vacancies ? `${n.total_vacancies.toLocaleString()} vacancies` : '';
  const salary = n.salary_range || '';
  const ageRange = (n.min_age && n.max_age) ? `${n.min_age}-${n.max_age} yrs` : '';
  const qual = n.educational_qualification
    ? (n.educational_qualification.length > 50
      ? n.educational_qualification.substring(0, 50) + '…'
      : n.educational_qualification)
    : '';

  return `
    <div class="notification-card fade-in" data-id="${n.id}">
      <div class="card-header">
        <div class="card-title">${escapeHtml(n.title)}</div>
        <div class="card-tags">
          ${statusBadge}
          ${eligBadge}
        </div>
      </div>
      <div class="card-org">${escapeHtml(n.organization_short_name || n.organization_name)}</div>
      <div class="card-meta">
        ${n.post_name ? `<span class="card-meta-item">📋 ${escapeHtml(n.post_name)}</span>` : ''}
        ${vacancies ? `<span class="card-meta-item">👥 ${vacancies}</span>` : ''}
        ${ageRange ? `<span class="card-meta-item">🎂 ${ageRange}</span>` : ''}
        ${qual ? `<span class="card-meta-item">🎓 ${escapeHtml(qual)}</span>` : ''}
      </div>
      <div class="card-meta">
        ${dateDisplay ? `<span class="card-meta-item">📅 ${dateDisplay}</span>` : ''}
        ${salary ? `<span class="card-meta-item">💰 ${escapeHtml(salary)}</span>` : ''}
        ${n.location ? `<span class="card-meta-item">📍 ${escapeHtml(n.location)}</span>` : ''}
      </div>
      <div class="card-footer">
        <div class="card-tags">
          <span class="badge badge-category">${categoryLabel}</span>
          ${verifyBadge}
        </div>
        <div style="display:flex;gap:4px;">
          ${n.official_notification_url
            ? `<button class="btn btn-sm btn-secondary card-link" data-url="${escapeHtml(n.official_notification_url)}">View Official</button>`
            : ''}
          <button class="btn btn-sm btn-ghost save-btn" data-id="${n.id}">
            ${n.is_saved ? '★ Saved' : '☆ Save'}
          </button>
        </div>
      </div>
    </div>`;
}

function updatePagination(data) {
  const pag = document.getElementById('pagination');
  if (data.total <= data.page_size) {
    pag.style.display = 'none';
    return;
  }
  pag.style.display = 'flex';
  document.getElementById('pageInfo').textContent =
    `Page ${data.page} of ${totalPages} (${data.total} total)`;
  document.getElementById('prevPage').disabled = data.page <= 1;
  document.getElementById('nextPage').disabled = !data.has_more;
}

// ===== Badge Helpers =====
function getStatusBadge(status) {
  const badges = {
    application_open: '<span class="badge badge-open">● Open</span>',
    closing_soon: '<span class="badge badge-closing">⏰ Closing Soon</span>',
    closed: '<span class="badge badge-closed">Closed</span>',
    upcoming: '<span class="badge badge-upcoming">🔜 Upcoming</span>',
    result_declared: '<span class="badge badge-result">📊 Result Declared</span>',
    admit_card_available: '<span class="badge badge-admit">🎫 Admit Card</span>',
    exam_date_announced: '<span class="badge badge-exam">📝 Exam Date</span>',
    cancelled: '<span class="badge badge-closed">❌ Cancelled</span>',
  };
  return badges[status] || `<span class="badge">${status}</span>`;
}

function getEligibilityBadge(match) {
  if (!match) return '';
  const badges = {
    likely_eligible: '<span class="badge badge-eligible">✓ Likely Eligible</span>',
    possibly_eligible: '<span class="badge badge-possibly">? Possibly Eligible</span>',
    not_eligible: '<span class="badge badge-ineligible">✗ Not Eligible</span>',
    insufficient_info: '<span class="badge badge-unknown">ℹ Insufficient Info</span>',
  };
  return badges[match] || '';
}

function getVerificationBadge(status) {
  const badges = {
    official_verified: '<span class="badge badge-verified">✓ Verified</span>',
    partially_verified: '<span class="badge badge-partial">~ Partial</span>',
    unverified: '<span class="badge badge-unverified">? Unverified</span>',
  };
  return badges[status] || '';
}

function getCategoryLabel(cat) {
  const labels = {
    banking: 'Banking', upsc: 'UPSC', ssc: 'SSC', railways: 'Railways',
    defence: 'Defence', central_govt: 'Central Govt', state_govt: 'State Govt',
    psu: 'PSU', teaching: 'Teaching', police: 'Police', research: 'Research',
    other: 'Other',
  };
  return labels[cat] || cat;
}

// ===== Utilities =====
function formatDate(dateStr) {
  try {
    const d = new Date(dateStr + 'T00:00:00+05:30');
    return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
  } catch { return dateStr; }
}

function formatDateTime(d) {
  return d.toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata',
  });
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

function showLoading(container) {
  container.innerHTML = `
    <div class="skeleton-card loading-skeleton" style="height:80px;margin:8px 0;"></div>
    <div class="skeleton-card loading-skeleton" style="height:80px;margin:8px 0;"></div>
    <div class="skeleton-card loading-skeleton" style="height:80px;margin:8px 0;"></div>`;
}

function showError(message) {
  document.getElementById('mainContent').style.display = 'none';
  document.getElementById('errorState').style.display = 'block';
  const errorEl = document.querySelector('.error-state p');
  if (errorEl) errorEl.textContent = message;
}
