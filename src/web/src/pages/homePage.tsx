import { useState, useEffect } from 'react';
import { Stack, PrimaryButton, Checkbox, Text, Spinner, MessageBar, MessageBarType, Link } from '@fluentui/react';
import { Activity } from '../models/activity';

const HomePage = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [selectedActivities, setSelectedActivities] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);
  const [merging, setMerging] = useState(false);
  const [mergeResult, setMergeResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/status`);
      if (response.ok) {
        setIsAuthenticated(true);
        loadActivities();
      }
    } catch (err) {
      console.log('Not authenticated');
    }
  };

  const loadActivities = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/activities`);
      if (response.ok) {
        const data = await response.json();
        setActivities(data);
      } else {
        setError('Failed to load activities');
      }
    } catch (err) {
      setError('Failed to load activities');
    } finally {
      setLoading(false);
    }
  };

  const handleAuth = () => {
    window.location.href = `${API_BASE_URL}/auth/url`;
  };

  const handleActivityToggle = (activityId: number, checked: boolean) => {
    const newSelected = new Set(selectedActivities);
    if (checked) {
      newSelected.add(activityId);
    } else {
      newSelected.delete(activityId);
    }
    setSelectedActivities(newSelected);
  };

  const handleMerge = async () => {
    if (selectedActivities.size < 2) {
      setError('Please select at least 2 activities to merge');
      return;
    }

    setMerging(true);
    setError(null);
    setMergeResult(null);

    try {
      const response = await fetch(`${API_BASE_URL}/merge`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          activity_ids: Array.from(selectedActivities),
        }),
      });

      if (response.ok) {
        const result = await response.json();
        setMergeResult(result.message);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to merge activities');
      }
    } catch (err) {
      setError('Failed to merge activities');
    } finally {
      setMerging(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <Stack horizontalAlign="center" verticalAlign="center" styles={{ root: { height: '100vh' } }}>
        <Stack tokens={{ childrenGap: 20 }} styles={{ root: { maxWidth: 400, textAlign: 'center' } }}>
          <Text variant="xxLarge">Strava Activity Merger</Text>
          <Text variant="medium">Merge multiple Strava activities into one</Text>
          <PrimaryButton text="Connect with Strava" onClick={handleAuth} />
        </Stack>
      </Stack>
    );
  }

  return (
    <Stack tokens={{ childrenGap: 20 }} styles={{ root: { padding: 20 } }}>
      <Text variant="xxLarge">Strava Activity Merger</Text>

      {error && (
        <MessageBar messageBarType={MessageBarType.error}>
          {error}
        </MessageBar>
      )}

      {mergeResult && (
        <MessageBar messageBarType={MessageBarType.success}>
          {mergeResult}
        </MessageBar>
      )}

      <Stack tokens={{ childrenGap: 10 }}>
        <Text variant="large">Select activities to merge:</Text>
        {loading ? (
          <Spinner label="Loading activities..." />
        ) : (
          <Stack tokens={{ childrenGap: 8 }}>
            {activities.map((activity) => (
              <Checkbox
                key={activity.id}
                label={`${activity.name} - ${new Date(activity.start_date).toLocaleDateString()} - ${activity.type}`}
                checked={selectedActivities.has(activity.id)}
                onChange={(_, checked) => handleActivityToggle(activity.id, checked || false)}
              />
            ))}
          </Stack>
        )}
      </Stack>

      <PrimaryButton
        text={merging ? "Merging..." : "Merge Selected Activities"}
        onClick={handleMerge}
        disabled={merging || selectedActivities.size < 2}
      />

      <Text variant="small">
        Selected: {selectedActivities.size} activities
      </Text>
    </Stack>
  );
};

export default HomePage;
