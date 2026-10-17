/**
 * ExamRadar India - Background Service Worker (Manifest V3)
 * Handles alarms, persistent alert deduplication, badge counts, and notifications.
 */

const DEFAULT_API_BASE = 'http://localhost:8000';
const ALARM_NAME = 'examradar-check';

// Note on Alarm Scheduling:
// Chrome alarms in Manifest V3 are scheduled by the browser's internal task runner.
// The runtime throttles background execution based on system idle state, battery saver mode,
// and background policy. An interval of 30 minutes represents a periodic schedule,
// not an exact-second guarantee.
const ALARM_INTERVAL_MINUTES = 30;

// Get configured API base URL
async function getApiBase() {
  const result = await chrome.storage.local.get(['apiBaseUrl']);
  return result.apiBaseUrl || DEFAULT_API_BASE;
}

// Ensure background alarm is registered
async function ensureAlarm() {
  try {
    const existing = await chrome.alarms.get(ALARM_NAME);
    if (!existing) {
      chrome.alarms.create(ALARM_NAME, {
        delayInMinutes: 1,
        periodInMinutes: ALARM_INTERVAL_MINUTES,
      });
      console.log(`ExamRadar: Registered alarm '${ALARM_NAME}' with interval ~${ALARM_INTERVAL_MINUTES} mins.`);
    }
  } catch (err) {
    console.error('ExamRadar: Failed to ensure alarm:', err);
  }
}

// Check for updates with persistent deduplication
async function checkForUpdates() {
  try {
    const apiBase = await getApiBase();
    const response = await fetch(`${apiBase}/api/v1/dashboard`);
    if (!response.ok) {
      console.warn(`ExamRadar: Backend returned status ${response.status}`);
      return;
    }

    const dashboard = await response.json();

    // Load persistent deduplication state & preferences
    const storage = await chrome.storage.local.get([
      'alertedNotificationIds',
      'alertedDeadlineIds',
      'alertedLifecycleIds',
      'alertsEnabled',
      'alertPreferences',
    ]);

    const alertedNotifSet = new Set(storage.alertedNotificationIds || []);
    const alertedDeadlineSet = new Set(storage.alertedDeadlineIds || []);
    const alertedLifecycleSet = new Set(storage.alertedLifecycleIds || []);
    const alertsEnabled = storage.alertsEnabled !== false; // enabled by default
    const prefs = storage.alertPreferences || {};

    // 1. Persistent Deduplication for New Notifications
    const recentItems = dashboard.recent_notifications || [];
    const unAlertedNew = recentItems.filter(item => !alertedNotifSet.has(item.id));

    if (alertsEnabled && unAlertedNew.length > 0 && prefs.new_matching !== false) {
      const eligibleOnly = prefs.only_eligible === true;
      const candidatesToAlert = eligibleOnly
        ? unAlertedNew.filter(item => item.eligibility_match === 'likely_eligible')
        : unAlertedNew;

      if (candidatesToAlert.length > 0) {
        const topItem = candidatesToAlert[0];
        const count = candidatesToAlert.length;
        const msg = count === 1
          ? `${topItem.title} (${topItem.organization_short_name || topItem.organization_name || 'Govt'})`
          : `${count} new recruitment notification(s) discovered matching your radar.`;

        chrome.notifications.create(`examradar-new-${topItem.id}`, {
          type: 'basic',
          iconUrl: 'icons/icon128.png',
          title: 'ExamRadar India - New Notification',
          message: msg,
          priority: 1,
        });
      }

      // Mark all new items as alerted so they never alert again across restarts
      unAlertedNew.forEach(item => alertedNotifSet.add(item.id));
    }

    // 2. Persistent Deduplication for Closing Soon Deadlines (within 3 days)
    const closingItems = dashboard.closing_soon_notifications || [];
    const urgentItems = closingItems.filter(n => {
      if (!n.application_end_date) return false;
      const endDate = new Date(n.application_end_date);
      const now = new Date();
      const daysLeft = Math.ceil((endDate - now) / (1000 * 60 * 60 * 24));
      return daysLeft >= 0 && daysLeft <= 3 && !alertedDeadlineSet.has(n.id);
    });

    if (alertsEnabled && urgentItems.length > 0 && prefs.deadline_3days !== false) {
      const topUrgent = urgentItems[0];
      const count = urgentItems.length;
      const msg = count === 1
        ? `Application for "${topUrgent.title}" is closing soon! Deadline: ${topUrgent.application_end_date}`
        : `${count} applications are closing within the next 3 days!`;

      chrome.notifications.create(`examradar-deadline-${topUrgent.id}`, {
        type: 'basic',
        iconUrl: 'icons/icon128.png',
        title: 'ExamRadar India - Closing Soon Alert',
        message: msg,
        priority: 2,
      });

      urgentItems.forEach(n => alertedDeadlineSet.add(n.id));
    }

    // 3. Update Badge Counter
    const badgeCount = dashboard.newly_discovered || 0;
    if (badgeCount > 0) {
      chrome.action.setBadgeText({ text: String(badgeCount) });
      chrome.action.setBadgeBackgroundColor({ color: '#FF6B35' });
    } else {
      chrome.action.setBadgeText({ text: '' });
    }

    // Persist deduplication state and dashboard cache
    await chrome.storage.local.set({
      dashboardData: dashboard,
      lastChecked: new Date().toISOString(),
      alertedNotificationIds: Array.from(alertedNotifSet).slice(-500), // retain last 500
      alertedDeadlineIds: Array.from(alertedDeadlineSet).slice(-500),
      alertedLifecycleIds: Array.from(alertedLifecycleSet).slice(-500),
    });
  } catch (error) {
    console.error('ExamRadar: Background update check failed:', error.message);
    await chrome.storage.local.set({
      lastError: error.message,
      lastChecked: new Date().toISOString(),
    });
  }
}

// Lifecycle: Install & Update
chrome.runtime.onInstalled.addListener(async () => {
  console.log('ExamRadar India extension installed/updated.');
  await ensureAlarm();
  await checkForUpdates();
});

// Lifecycle: Browser Startup
chrome.runtime.onStartup.addListener(async () => {
  console.log('ExamRadar India extension started.');
  await ensureAlarm();
  await checkForUpdates();
});

// Alarm Trigger Listener
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM_NAME) {
    console.log(`ExamRadar: Periodic alarm triggered (~${ALARM_INTERVAL_MINUTES} min schedule).`);
    checkForUpdates();
  }
});

// Handle Notification Clicks
chrome.notifications.onClicked.addListener((notificationId) => {
  if (notificationId.startsWith('examradar-')) {
    chrome.action.openPopup?.() || chrome.tabs.create({ url: 'dashboard.html' });
  }
});

// Message Passing Router
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'refresh') {
    checkForUpdates().then(() => sendResponse({ status: 'done' }));
    return true; // keep channel open for async response
  }
  if (message.action === 'openDashboard') {
    chrome.tabs.create({ url: 'dashboard.html' });
    sendResponse({ status: 'opened' });
  }
  if (message.action === 'openUrl') {
    try {
      const url = new URL(message.url);
      if (url.protocol === 'https:' || url.protocol === 'http:') {
        chrome.tabs.create({ url: message.url });
      }
    } catch (e) {
      console.error('Invalid URL requested:', message.url);
    }
    sendResponse({ status: 'opened' });
  }
});
