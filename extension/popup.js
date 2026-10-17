/**
 * ExamRadar India - Popup Controller
 * Manages the popup dashboard, tabs, filters, and notification cards.
 */

const api = new ExamRadarAPI();
let currentTab = 'recommended';
let currentPage = 1;
let currentFilters = {};
let totalPages = 1;

let cachedNotifications = [];
let hasRenderedContent = false;

// ===== Initialization =====
document.addEventListener('DOMContentLoaded', async () => {
  initTheme();
  initEventListeners();

  // 1. Instant 0-second render from local storage or bundled cache
  await initOfflineCache();

  // 2. Silently fetch live updates in the background
  fetchLiveUpdates();
});

// ===== Offline Cache & Instant Rendering =====
async function initOfflineCache() {
  let storedNotifs = [];
  let storedStats = null;
  let storedCats = null;

  if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
    try {
      const res = await chrome.storage.local.get(['cachedNotifications', 'cachedDashboard', 'cachedCategories']);
      storedNotifs = res.cachedNotifications || [];
      storedStats = res.cachedDashboard || null;
      storedCats = res.cachedCategories || null;
    } catch (e) {
      console.warn('ExamRadar: Error reading cache:', e);
    }
  }

  // Fallback to bundled verified notifications if no storage yet
  if ((!storedNotifs || storedNotifs.length === 0) && window.EXAMRADAR_BUNDLED_NOTIFICATIONS) {
    storedNotifs = window.EXAMRADAR_BUNDLED_NOTIFICATIONS;
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      chrome.storage.local.set({ cachedNotifications: storedNotifs });
    }
  }

  cachedNotifications = storedNotifs || [];

  // Populate categories from cache or default list
  if (storedCats && storedCats.length) {
    populateCategoryDropdown(storedCats);
  } else {
    populateDefaultCategories();
  }

  // Render stats from cache or compute from cached notices
  if (storedStats) {
    renderStats(storedStats, true);
  } else if (cachedNotifications.length > 0) {
    const stats = computeStatsFromItems(cachedNotifications);
    renderStats(stats, true);
  }

  // Render notifications instantly
  if (cachedNotifications.length > 0) {
    renderFilteredCachedItems();
    hasRenderedContent = true;
    document.getElementById('errorState').style.display = 'none';
    document.getElementById('mainContent').style.display = 'block';
  }
}

function renderStats(data, isCached = false) {
  document.getElementById('statOpen').textContent = data.total_open ?? data.open ?? 0;
  document.getElementById('statNew').textContent = data.newly_discovered ?? data.new ?? 0;
  document.getElementById('statMatch').textContent = data.matching_profile ?? data.match ?? 0;
  document.getElementById('statClosing').textContent = data.closing_soon ?? data.closing ?? 0;

  const lastUpdatedEl = document.getElementById('lastUpdated');
  if (data.last_updated) {
    const d = new Date(data.last_updated);
    lastUpdatedEl.textContent = `Last updated: ${formatDateTime(d)}${isCached ? ' (Cached)' : ''}`;
  } else if (isCached) {
    lastUpdatedEl.textContent = 'Showing verified notices (Connecting...)';
  } else {
    lastUpdatedEl.textContent = 'Live data active';
  }
}

function computeStatsFromItems(items) {
  const verified = (items || []).filter(n => !n.is_synthetic);
  const now = new Date();
  let openCount = 0;
  let closingCount = 0;

  verified.forEach(item => {
    if (item.application_status === 'application_open') openCount++;
    if (item.application_end_date) {
      const end = new Date(item.application_end_date);
      const diffDays = Math.ceil((end - now) / (1000 * 60 * 60 * 24));
      if (diffDays >= 0 && diffDays <= 7) closingCount++;
    }
  });

  return {
    total_open: openCount,
    newly_discovered: verified.length,
    matching_profile: verified.length,
    closing_soon: closingCount,
    last_updated: null,
  };
}

function filterCachedItems(items, tab, search, category, sortBy) {
  let list = (items || []).filter(n => !n.is_synthetic);

  // Tab filter
  if (tab === 'open') {
    list = list.filter(n => n.application_status === 'application_open');
  } else if (tab === 'closing') {
    const now = new Date();
    list = list.filter(n => {
      if (!n.application_end_date) return false;
      const end = new Date(n.application_end_date);
      const diff = Math.ceil((end - now) / (1000 * 60 * 60 * 24));
      return diff >= 0 && diff <= 10;
    });
  } else if (tab === 'results') {
    list = list.filter(n => n.application_status === 'result_declared');
  }

  // Search filter
  if (search && search.trim()) {
    const q = search.trim().toLowerCase();
    list = list.filter(n =>
      (n.title && n.title.toLowerCase().includes(q)) ||
      (n.post_name && n.post_name.toLowerCase().includes(q)) ||
      (n.advertisement_number && n.advertisement_number.toLowerCase().includes(q)) ||
      (n.organization_short_name && n.organization_short_name.toLowerCase().includes(q)) ||
      (n.organization_name && n.organization_name.toLowerCase().includes(q))
    );
  }

  // Category filter
  if (category) {
    list = list.filter(n => n.category === category);
  }

  // Sort
  if (sortBy === 'deadline') {
    list.sort((a, b) => new Date(a.application_end_date || '9999-12-31') - new Date(b.application_end_date || '9999-12-31'));
  } else if (sortBy === 'organization') {
    list.sort((a, b) => (a.organization_short_name || '').localeCompare(b.organization_short_name || ''));
  } else {
    // Newest first (id desc)
    list.sort((a, b) => (b.id || 0) - (a.id || 0));
  }

  return list;
}

function renderFilteredCachedItems() {
  const container = document.getElementById('notificationsList');
  const search = document.getElementById('searchInput').value;
  const category = document.getElementById('categoryFilter').value;
  const sortBy = document.getElementById('sortFilter').value;

  const filtered = filterCachedItems(cachedNotifications, currentTab, search, category, sortBy);
  const pageSize = 15;
  totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  if (currentPage > totalPages) currentPage = 1;

  const start = (currentPage - 1) * pageSize;
  const pagedItems = filtered.slice(start, start + pageSize);

  renderNotifications(container, pagedItems);
  updatePagination({ total: filtered.length, page: currentPage, page_size: pageSize });
}

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
  document.getElementById('refreshBtn')?.addEventListener('click', refresh);
  document.getElementById('themeBtn')?.addEventListener('click', toggleTheme);
  document.getElementById('dashboardBtn')?.addEventListener('click', () => {
    chrome.runtime.sendMessage({ action: 'openDashboard' });
  });
  document.getElementById('settingsBtn')?.addEventListener('click', () => {
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
      if (cachedNotifications && cachedNotifications.length > 0) {
        renderFilteredCachedItems();
      }
      loadNotifications(false);
    });
  });

  // Filters
  document.getElementById('searchInput')?.addEventListener('input', debounce(() => {
    currentPage = 1;
    if (cachedNotifications && cachedNotifications.length > 0) {
      renderFilteredCachedItems();
    }
    loadNotifications(false);
  }, 300));

  document.getElementById('categoryFilter')?.addEventListener('change', () => {
    currentPage = 1;
    if (cachedNotifications && cachedNotifications.length > 0) {
      renderFilteredCachedItems();
    }
    loadNotifications(false);
  });

  document.getElementById('sortFilter')?.addEventListener('change', () => {
    currentPage = 1;
    if (cachedNotifications && cachedNotifications.length > 0) {
      renderFilteredCachedItems();
    }
    loadNotifications(false);
  });

  // Pagination
  document.getElementById('prevPage')?.addEventListener('click', () => {
    if (currentPage > 1) {
      currentPage--;
      if (cachedNotifications && cachedNotifications.length > 0) {
        renderFilteredCachedItems();
      } else {
        loadNotifications(true);
      }
    }
  });
  document.getElementById('nextPage')?.addEventListener('click', () => {
    if (currentPage < totalPages) {
      currentPage++;
      if (cachedNotifications && cachedNotifications.length > 0) {
        renderFilteredCachedItems();
      } else {
        loadNotifications(true);
      }
    }
  });
}

function populateCategoryDropdown(categories) {
  const select = document.getElementById('categoryFilter');
  if (!select) return;
  const currentVal = select.value;
  select.innerHTML = '<option value="">All Categories</option>';
  categories.forEach(cat => {
    const option = document.createElement('option');
    option.value = cat.value;
    option.textContent = cat.label;
    if (cat.value === currentVal) option.selected = true;
    select.appendChild(option);
  });
}

function populateDefaultCategories() {
  const defaults = [
    { value: 'banking', label: 'Banking' },
    { value: 'upsc', label: 'UPSC' },
    { value: 'ssc', label: 'SSC' },
    { value: 'railways', label: 'Railways' },
    { value: 'defence', label: 'Defence' },
    { value: 'central_govt', label: 'Central Govt' },
    { value: 'state_govt', label: 'State Govt' },
    { value: 'psu', label: 'PSU' },
    { value: 'teaching', label: 'Teaching' },
    { value: 'police', label: 'Police' },
    { value: 'research', label: 'Research' }
  ];
  populateCategoryDropdown(defaults);
}

// ===== Live Data Fetchers =====
async function loadDashboard() {
  try {
    const data = await api.getDashboard();
    renderStats(data, false);
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      chrome.storage.local.set({ cachedDashboard: data });
    }
    document.getElementById('errorState').style.display = 'none';
    document.getElementById('mainContent').style.display = 'block';
  } catch (error) {
    if (!hasRenderedContent) {
      showError(error.message);
    }
  }
}

async function loadCategories() {
  try {
    const data = await api.getCategories();
    if (data && data.categories) {
      populateCategoryDropdown(data.categories);
      if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
        chrome.storage.local.set({ cachedCategories: data.categories });
      }
    }
  } catch (e) {
    console.warn('ExamRadar: Using fallback categories:', e.message);
  }
}

async function loadNotifications(showSkeleton = true) {
  const container = document.getElementById('notificationsList');
  if (!hasRenderedContent && showSkeleton) {
    showLoading(container);
  }

  const params = {
    page: currentPage,
    page_size: 15,
    search: document.getElementById('searchInput')?.value || undefined,
    category: document.getElementById('categoryFilter')?.value || undefined,
    sort_by: document.getElementById('sortFilter')?.value || 'newest',
  };

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
    let data = await api.getNotifications(params);
    if (currentTab === 'recommended' && (!data.items || data.items.length === 0)) {
      const fallbackParams = { ...params, eligibility: undefined, sort_by: 'newest' };
      const fallbackData = await api.getNotifications(fallbackParams).catch(() => null);
      if (fallbackData && fallbackData.items && fallbackData.items.length > 0) {
        data = fallbackData;
      }
    }

    if (data && data.items && data.items.length > 0) {
      // Merge into cachedNotifications
      const incoming = data.items.filter(n => !n.is_synthetic);
      const existingIds = new Set(incoming.map(n => n.id));
      const rest = cachedNotifications.filter(n => !existingIds.has(n.id));
      cachedNotifications = [...incoming, ...rest];

      if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
        chrome.storage.local.set({ cachedNotifications });
      }

      totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
      renderNotifications(container, data.items);
      updatePagination(data);
      hasRenderedContent = true;
    } else if (!hasRenderedContent) {
      renderNotifications(container, []);
    }

    document.getElementById('errorState').style.display = 'none';
    document.getElementById('mainContent').style.display = 'block';
  } catch (error) {
    console.warn('ExamRadar: Live notification fetch notice:', error.message);
    if (hasRenderedContent) {
      renderFilteredCachedItems();
    } else {
      showError(error.message);
    }
  }
}

async function refresh() {
  const btn = document.getElementById('refreshBtn');
  if (btn) {
    btn.style.opacity = '0.5';
    btn.disabled = true;
  }

  try {
    await chrome.runtime.sendMessage({ action: 'refresh' });
    await loadDashboard();
    await loadNotifications(false);
  } catch (e) {
    console.warn('Refresh notice:', e.message);
  } finally {
    if (btn) {
      btn.style.opacity = '1';
      btn.disabled = false;
    }
  }
}

// ===== Background Live Updates =====
async function fetchLiveUpdates() {
  try {
    await loadCategories();
    await loadDashboard();
    await loadNotifications(false); // false = silent update, don't flash blank skeleton
  } catch (err) {
    console.warn('ExamRadar: Live update notice, keeping cached view active:', err.message);
    if (hasRenderedContent) {
      const lastUpdatedEl = document.getElementById('lastUpdated');
      if (lastUpdatedEl && !lastUpdatedEl.textContent.includes('Cached')) {
        lastUpdatedEl.textContent += ' (Offline Mode)';
      }
    } else {
      showError(err.message);
    }
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
