/**
 * ExamRadar India - API Service
 * Handles all communication with the backend.
 */

const DEFAULT_API_BASE = 'https://examradar-india.onrender.com';

class ExamRadarAPI {
  constructor() {
    this.baseUrl = DEFAULT_API_BASE;
  }

  async getBaseUrl() {
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      try {
        const result = await chrome.storage.local.get(['apiBaseUrl']);
        if (result && result.apiBaseUrl) {
          this.baseUrl = result.apiBaseUrl;
        }
      } catch (e) {
        // use default
      }
    }
    return this.baseUrl;
  }

  async _fetch(endpoint, options = {}) {
    await this.getBaseUrl();
    const url = `${this.baseUrl}${endpoint}`;
    const defaults = {
      headers: { 'Content-Type': 'application/json' },
    };

    const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    const timeoutId = controller ? setTimeout(() => controller.abort(), options.timeoutMs || 15000) : null;

    const config = {
      ...defaults,
      ...options,
      headers: {
        ...defaults.headers,
        ...(options.headers || {}),
      },
      signal: controller ? controller.signal : undefined,
    };

    try {
      const response = await fetch(url, config);
      if (timeoutId) clearTimeout(timeoutId);
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      if (timeoutId) clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        throw new Error('Connection timed out. Server may be starting up.');
      }
      if (error.name === 'TypeError' && error.message.includes('fetch')) {
        throw new Error('Backend unavailable. Please check internet connection.');
      }
      throw error;
    }
  }

  // Health
  async health() { return this._fetch('/api/v1/health'); }

  // Dashboard
  async getDashboard() { return this._fetch('/api/v1/dashboard'); }

  // Notifications
  async getNotifications(params = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== '') query.set(k, v);
    });
    return this._fetch(`/api/v1/notifications?${query.toString()}`);
  }

  async getNotification(id) { return this._fetch(`/api/v1/notifications/${id}`); }
  async getNewNotifications(page = 1) {
    return this._fetch(`/api/v1/notifications/new?page=${page}`);
  }
  async getClosingSoon(days = 7) {
    return this._fetch(`/api/v1/notifications/closing-soon?days=${days}`);
  }
  async getResults() { return this._fetch('/api/v1/notifications/results'); }
  async getAdmitCards() { return this._fetch('/api/v1/notifications/admit-cards'); }

  // Categories
  async getCategories() { return this._fetch('/api/v1/categories'); }
  async getOrganizations() { return this._fetch('/api/v1/organizations'); }

  // Sources
  async getSources() { return this._fetch('/api/v1/sources'); }
  async getSourceStatus() { return this._fetch('/api/v1/sources/status'); }
  async getDiscoveryStatus() { return this._fetch('/api/v1/discovery/status'); }
  async triggerDiscovery(sourceId = null) {
    const endpoint = sourceId ? `/api/v1/discovery/run?source_id=${encodeURIComponent(sourceId)}` : '/api/v1/discovery/run';
    return this._fetch(endpoint, {
      method: 'POST',
      headers: { 'x-admin-key': 'examradar-admin' },
    });
  }
  async discoverSource(sourceId) {
    return this._fetch(`/api/v1/sources/${encodeURIComponent(sourceId)}/discover`, {
      method: 'POST',
      headers: { 'x-admin-key': 'examradar-admin' },
    });
  }

  // Profile
  async getProfile() { return this._fetch('/api/v1/profile'); }
  async updateProfile(data) {
    return this._fetch('/api/v1/profile', {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }
  async deleteProfile() {
    return this._fetch('/api/v1/profile', { method: 'DELETE' });
  }

  // Saved
  async getSaved() { return this._fetch('/api/v1/saved'); }
  async saveNotification(id) {
    return this._fetch(`/api/v1/saved/${id}`, { method: 'POST' });
  }
  async unsaveNotification(id) {
    return this._fetch(`/api/v1/saved/${id}`, { method: 'DELETE' });
  }
  async markApplied(id) {
    return this._fetch(`/api/v1/saved/${id}/applied`, { method: 'PUT' });
  }

  // Alerts
  async getAlerts() { return this._fetch('/api/v1/alerts'); }
  async updateAlerts(prefs) {
    return this._fetch('/api/v1/alerts/preferences', {
      method: 'PUT',
      body: JSON.stringify(prefs),
    });
  }

  // Report
  async reportNotification(id, data) {
    return this._fetch(`/api/v1/notifications/${id}/report`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }
}

// Export for use in both popup and dashboard
if (typeof window !== 'undefined') {
  window.ExamRadarAPI = ExamRadarAPI;
}
