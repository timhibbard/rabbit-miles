import { useEffect, useState } from 'react';
import { fetchMe, resetTrailMatching, updateActivities, updateUserSettings } from '../utils/api';

// Common US timezones for the dropdown
const TIMEZONES = [
  { value: 'America/New_York', label: 'Eastern Time (ET)' },
  { value: 'America/Chicago', label: 'Central Time (CT)' },
  { value: 'America/Denver', label: 'Mountain Time (MT)' },
  { value: 'America/Phoenix', label: 'Arizona (no DST)' },
  { value: 'America/Los_Angeles', label: 'Pacific Time (PT)' },
  { value: 'America/Anchorage', label: 'Alaska Time (AKT)' },
  { value: 'Pacific/Honolulu', label: 'Hawaii Time (HT)' },
];

function Settings() {
  const [authState, setAuthState] = useState({
    loading: true,
    isConnected: false,
    showOnLeaderboards: true,
    timezone: null,
    email: '',
    notifyActivity: false,
    notifyWeeklySummary: false,
  });
  const [resetting, setResetting] = useState(false);
  const [updatingActivities, setUpdatingActivities] = useState(false);
  const [updatingLeaderboardSettings, setUpdatingLeaderboardSettings] = useState(false);
  const [updatingTimezone, setUpdatingTimezone] = useState(false);
  const [emailInput, setEmailInput] = useState('');
  const [updatingEmail, setUpdatingEmail] = useState(false);
  const [emailError, setEmailError] = useState('');
  const [emailSuccess, setEmailSuccess] = useState('');
  const [updatingNotifications, setUpdatingNotifications] = useState(false);

  useEffect(() => {
    // Check if user is connected via /me endpoint
    const checkConnection = async () => {
      const result = await fetchMe();
      const email = result.user?.email || '';
      setAuthState({
        loading: false,
        isConnected: result.success,
        showOnLeaderboards: result.user?.show_on_leaderboards ?? true,
        timezone: result.user?.timezone || 'America/New_York', // Default to Eastern
        email,
        notifyActivity: result.user?.notify_activity ?? false,
        notifyWeeklySummary: result.user?.notify_weekly_summary ?? false,
      });
      setEmailInput(email);
    };
    
    checkConnection();
  }, []);

  const handleDisconnect = () => {
    if (window.confirm('Are you sure you want to disconnect your Strava account?')) {
      // TODO: Call disconnect API endpoint when it becomes available
      // For now, just show a message
      alert('Disconnect functionality will be available soon. Please use the footer contact link to request account disconnection.');
    }
  };

  const handleEmailSave = async (e) => {
    e.preventDefault();
    setEmailError('');
    setEmailSuccess('');
    setUpdatingEmail(true);
    try {
      const result = await updateUserSettings({ email: emailInput.trim() });
      if (result.success) {
        setAuthState(prev => ({ ...prev, email: result.data.email || '' }));
        setEmailSuccess('Email address saved.');
      } else {
        setEmailError(result.error || 'Failed to save email address.');
      }
    } catch (error) {
      console.error('Error saving email:', error);
      setEmailError('An unexpected error occurred. Please try again.');
    } finally {
      setUpdatingEmail(false);
    }
  };

  const handleNotificationToggle = async (field, newValue) => {
    setUpdatingNotifications(true);
    try {
      const result = await updateUserSettings({ [field]: newValue });
      if (result.success) {
        setAuthState(prev => ({
          ...prev,
          notifyActivity: result.data.notify_activity ?? prev.notifyActivity,
          notifyWeeklySummary: result.data.notify_weekly_summary ?? prev.notifyWeeklySummary,
        }));
      } else {
        alert(`Failed to update notification settings: ${result.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error updating notification settings:', error);
      alert('An unexpected error occurred. Please try again.');
    } finally {
      setUpdatingNotifications(false);
    }
  };

  const handleResetTrailMatching = async () => {
    if (!window.confirm('Are you sure you want to reset trail matching for all your activities? This will mark all your activities as unprocessed for trail matching.')) {
      return;
    }

    setResetting(true);
    try {
      const result = await resetTrailMatching();
      if (result.success) {
        alert(`Success! ${result.data.activities_reset} activities have been reset for trail matching.`);
      } else {
        alert(`Failed to reset trail matching: ${result.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error resetting trail matching:', error);
      alert('An unexpected error occurred. Please try again.');
    } finally {
      setResetting(false);
    }
  };

  const handleUpdateActivities = async () => {
    if (!window.confirm('This will refresh all your activities from Strava. This may take a few moments. Continue?')) {
      return;
    }

    setUpdatingActivities(true);
    try {
      const result = await updateActivities();
      if (result.success) {
        const { stored, failed, total_activities } = result.data;
        alert(`Success! Updated ${stored} activities out of ${total_activities} fetched from Strava.${failed > 0 ? ` (${failed} failed)` : ''}`);
      } else {
        alert(`Failed to update activities: ${result.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error updating activities:', error);
      alert('An unexpected error occurred. Please try again.');
    } finally {
      setUpdatingActivities(false);
    }
  };

  const handleToggleLeaderboards = async (newValue) => {
    setUpdatingLeaderboardSettings(true);
    try {
      const result = await updateUserSettings({ show_on_leaderboards: newValue });
      if (result.success) {
        setAuthState(prev => ({
          ...prev,
          showOnLeaderboards: result.data.show_on_leaderboards
        }));
      } else {
        alert(`Failed to update leaderboard settings: ${result.error || 'Unknown error'}`);
        // Revert on error
      }
    } catch (error) {
      console.error('Error updating leaderboard settings:', error);
      alert('An unexpected error occurred. Please try again.');
    } finally {
      setUpdatingLeaderboardSettings(false);
    }
  };

  const handleTimezoneChange = async (event) => {
    const newTimezone = event.target.value;
    setUpdatingTimezone(true);
    try {
      const result = await updateUserSettings({ timezone: newTimezone });
      if (result.success) {
        setAuthState(prev => ({
          ...prev,
          timezone: result.data.timezone || newTimezone
        }));
      } else {
        alert(`Failed to update timezone: ${result.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error updating timezone:', error);
      alert('An unexpected error occurred. Please try again.');
    } finally {
      setUpdatingTimezone(false);
    }
  };

  if (authState.loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-orange-600 mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">
          Settings
        </h1>

        <div className="bg-white rounded-lg shadow">
          {/* Strava Connection Section */}
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              Strava Connection
            </h2>
            
            {authState.isConnected ? (
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <div className="w-12 h-12 bg-orange-500 rounded-full flex items-center justify-center mr-4">
                    <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066m-7.008-5.599l2.836 5.598h4.172L10.463 0l-7 13.828h4.169"></path>
                    </svg>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      Connected to Strava
                    </p>
                    <p className="text-sm text-gray-500">
                      Your Strava data is synced with RabbitMiles
                    </p>
                  </div>
                </div>
                <button
                  onClick={handleDisconnect}
                  className="px-4 py-2 border border-red-300 text-red-700 rounded-md hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                >
                  Disconnect
                </button>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    Not Connected
                  </p>
                  <p className="text-sm text-gray-500">
                    Connect your Strava account to start tracking your miles
                  </p>
                </div>
                <a
                  href="/connect"
                  className="px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-orange-500"
                >
                  Connect Strava
                </a>
              </div>
            )}
          </div>

          {/* Units Section */}
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              Units
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Distance Unit
                </label>
                <select
                  className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-orange-500 focus:border-orange-500 sm:text-sm rounded-md"
                  defaultValue="miles"
                >
                  <option value="miles">Miles</option>
                  <option value="kilometers">Kilometers</option>
                </select>
              </div>
            </div>
          </div>

          {/* Timezone Section */}
          {authState.isConnected && (
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                Timezone
              </h2>
              <div>
                <p className="text-sm text-gray-600 mb-4">
                  Set your timezone to ensure accurate weekly, monthly, and yearly statistics. This affects when your weeks start (Monday at midnight in your timezone) and leaderboard calculations.
                </p>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Your Timezone
                </label>
                <select
                  value={authState.timezone || 'America/New_York'}
                  onChange={handleTimezoneChange}
                  disabled={updatingTimezone}
                  className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-orange-500 focus:border-orange-500 sm:text-sm rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {TIMEZONES.map((tz) => (
                    <option key={tz.value} value={tz.value}>
                      {tz.label}
                    </option>
                  ))}
                </select>
                {updatingTimezone && (
                  <p className="text-sm text-gray-500 mt-2">Updating timezone...</p>
                )}
              </div>
            </div>
          )}

          {/* Activities Section */}
          {authState.isConnected && (
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                Activities
              </h2>
              <div className="space-y-4">
                <div>
                  <h3 className="text-sm font-medium text-gray-900 mb-2">
                    Refresh Activities from Strava
                  </h3>
                  <p className="text-sm text-gray-600 mb-4">
                    Fetch the latest activities from Strava and update your database with any changes (including athlete count for group activities).
                  </p>
                  <button
                    onClick={handleUpdateActivities}
                    disabled={updatingActivities}
                    className="px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-orange-500 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {updatingActivities ? 'Updating...' : 'Refresh Activities'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Trail Matching Section */}
          {authState.isConnected && (
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                Trail Matching
              </h2>
              <div>
                <p className="text-sm text-gray-600 mb-4">
                  Reset trail matching to re-process all your activities. This will mark all your activities as unprocessed for the trail matcher.
                </p>
                <button
                  onClick={handleResetTrailMatching}
                  disabled={resetting}
                  className="px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-orange-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {resetting ? 'Resetting...' : 'Reset Trail Matching'}
                </button>
              </div>
            </div>
          )}

          {/* Leaderboard Privacy Section */}
          {authState.isConnected && (
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                Leaderboard Privacy
              </h2>
              <div>
                <p className="text-sm text-gray-600 mb-4">
                  Control whether your activities appear on the leaderboard. When enabled, your running stats will be visible to other users on the leaderboard. When disabled, your activities will be private and won't contribute to leaderboard rankings.
                </p>
                <label className="flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={authState.showOnLeaderboards}
                    onChange={(e) => handleToggleLeaderboards(e.target.checked)}
                    disabled={updatingLeaderboardSettings}
                    className="sr-only peer"
                  />
                  <div className="relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-orange-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-orange-600"></div>
                  <span className="ms-3 text-sm font-medium text-gray-900">
                    {authState.showOnLeaderboards ? 'Show on leaderboard' : 'Hidden from leaderboard'}
                    {updatingLeaderboardSettings && ' (updating...)'}
                  </span>
                </label>
              </div>
            </div>
          )}

          {/* Profile Section */}
          {authState.isConnected && (
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                Profile
              </h2>
              <p className="text-sm text-gray-600 mb-4">
                Add your email address to receive notifications about your activities and weekly summaries.
              </p>
              <form onSubmit={handleEmailSave} className="space-y-4">
                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                    Email Address
                  </label>
                  <input
                    id="email"
                    type="email"
                    value={emailInput}
                    onChange={(e) => { setEmailInput(e.target.value); setEmailError(''); setEmailSuccess(''); }}
                    placeholder="you@example.com"
                    className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-orange-500 focus:border-orange-500 sm:text-sm"
                  />
                  {emailError && <p className="mt-1 text-sm text-red-600">{emailError}</p>}
                  {emailSuccess && <p className="mt-1 text-sm text-green-600">{emailSuccess}</p>}
                </div>
                <button
                  type="submit"
                  disabled={updatingEmail}
                  className="px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-orange-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {updatingEmail ? 'Saving...' : 'Save Email'}
                </button>
              </form>
            </div>
          )}

          {/* Notifications Section */}
          {authState.isConnected && (
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                Email Notifications
              </h2>
              {!authState.email && (
                <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-3 mb-4">
                  Add an email address in the Profile section above to enable notifications.
                </p>
              )}
              <div className="space-y-4">
                <label className="flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={authState.notifyActivity}
                    onChange={(e) => handleNotificationToggle('notify_activity', e.target.checked)}
                    disabled={updatingNotifications || !authState.email}
                    className="sr-only peer"
                  />
                  <div className={`relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-orange-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-orange-600 ${!authState.email ? 'opacity-50 cursor-not-allowed' : ''}`}></div>
                  <div className="ms-3">
                    <span className="text-sm font-medium text-gray-900">Activity &amp; milestone alerts</span>
                    <p className="text-xs text-gray-500">Get notified when a new activity is processed or you reach a new mile threshold.</p>
                  </div>
                </label>
                <label className="flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={authState.notifyWeeklySummary}
                    onChange={(e) => handleNotificationToggle('notify_weekly_summary', e.target.checked)}
                    disabled={updatingNotifications || !authState.email}
                    className="sr-only peer"
                  />
                  <div className={`relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-orange-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-orange-600 ${!authState.email ? 'opacity-50 cursor-not-allowed' : ''}`}></div>
                  <div className="ms-3">
                    <span className="text-sm font-medium text-gray-900">Weekly summary</span>
                    <p className="text-xs text-gray-500">Receive a weekly email summarizing your running activity.</p>
                  </div>
                </label>
                {updatingNotifications && <p className="text-sm text-gray-500">Updating...</p>}
              </div>
            </div>
          )}

          {/* About Section */}
          <div className="p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              About
            </h2>
            <div className="text-sm text-gray-600">
              <p className="mb-2">
                <strong>RabbitMiles</strong> - Version 1.0.0
              </p>
              <p>
                Track your running miles with Strava integration.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Settings;
