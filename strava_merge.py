#!/usr/bin/env python3

import os
import sys
from datetime import datetime, timedelta
import requests
from stravalib import Client
from stravalib.model import Stream
import xml.etree.ElementTree as ET

def get_access_token():
    token = os.getenv('STRAVA_ACCESS_TOKEN')
    refresh_token = os.getenv('STRAVA_REFRESH_TOKEN')
    expires_at = int(os.getenv('STRAVA_TOKEN_EXPIRES', 0))
    if token:
        print("Using access token from environment variable.")
        return token, refresh_token, expires_at
    
    # Perform OAuth flow
    client_id = input("Enter your Strava client ID: ")
    client_secret = input("Enter your Strava client secret: ")
    
    client = Client()
    authorize_url = client.authorization_url(
        client_id=client_id,
        redirect_uri='http://localhost',
        scope=['activity:read', 'activity:write']
    )
    
    print(f"Go to this URL in your browser and authorize the app: {authorize_url}")
    print("After authorization, you'll be redirected to http://localhost?code=...")
    print("Copy the 'code' parameter from the URL and paste it here.")
    
    code = input("Enter the authorization code: ")
    
    token_response = client.exchange_code_for_token(
        client_id=client_id,
        client_secret=client_secret,
        code=code
    )
    
    access_token = token_response['access_token']
    refresh_token = token_response['refresh_token']
    expires_at = token_response.get('expires_at', 0)
    print(f"Access token obtained: {access_token}")
    print(f"Refresh token obtained: {refresh_token}")
    print(f"Expires at: {expires_at}")
    print("You can set these as STRAVA_ACCESS_TOKEN, STRAVA_REFRESH_TOKEN, and STRAVA_TOKEN_EXPIRES environment variables for future runs.")
    
    return access_token, refresh_token, expires_at

def list_recent_activities(client):
    after = datetime.now() - timedelta(days=7)
    activities = list(client.get_activities(after=after))
    for i, activity in enumerate(activities):
        print(f"{i+1}: {activity.name} - {activity.start_date_local}")
    return activities

def download_fit(activity_id, access_token, filename):
    # Note: Strava API does not provide direct FIT download.
    # Users must download manually from the web interface.
    pass

def merge_activities(client, act1_id, act2_id, output_file):
    # Get activity details
    act1 = client.get_activity(act1_id)
    act2 = client.get_activity(act2_id)
    
    sport = act1.type
    
    # Get streams
    streams1 = client.get_activity_streams(act1_id, types=['time', 'latlng', 'distance', 'altitude', 'heartrate', 'cadence', 'watts'])
    streams2 = client.get_activity_streams(act2_id, types=['time', 'latlng', 'distance', 'altitude', 'heartrate', 'cadence', 'watts'])
    
    def create_points(streams, start_time):
        points = []
        times = streams.get('time', Stream()).data if 'time' in streams else []
        latlngs = streams.get('latlng', Stream()).data if 'latlng' in streams else []
        distances = streams.get('distance', Stream()).data if 'distance' in streams else []
        altitudes = streams.get('altitude', Stream()).data if 'altitude' in streams else []
        heartrates = streams.get('heartrate', Stream()).data if 'heartrate' in streams else []
        cadences = streams.get('cadence', Stream()).data if 'cadence' in streams else []
        wattss = streams.get('watts', Stream()).data if 'watts' in streams else []
        
        for i in range(len(times)):
            point = {
                'time': start_time + timedelta(seconds=times[i]),
                'lat': latlngs[i][0] if i < len(latlngs) else None,
                'lon': latlngs[i][1] if i < len(latlngs) else None,
                'distance': distances[i] if i < len(distances) else None,
                'altitude': altitudes[i] if i < len(altitudes) else None,
                'heartrate': heartrates[i] if i < len(heartrates) else None,
                'cadence': cadences[i] if i < len(cadences) else None,
                'watts': wattss[i] if i < len(wattss) else None,
            }
            points.append(point)
        return points
    
    points1 = create_points(streams1, act1.start_date)
    points2 = create_points(streams2, act2.start_date)
    
    # Offset distances for second activity
    if points1 and points2:
        max_dist1 = max((p['distance'] for p in points1 if p['distance'] is not None), default=0)
        for p in points2:
            if p['distance'] is not None:
                p['distance'] += max_dist1
    
    all_points = points1 + points2
    all_points.sort(key=lambda p: p['time'])
    
    # Create TCX
    root = ET.Element("TrainingCenterDatabase", xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2")
    activities_elem = ET.SubElement(root, "Activities")
    activity_elem = ET.SubElement(activities_elem, "Activity", Sport=sport)
    id_elem = ET.SubElement(activity_elem, "Id")
    id_elem.text = datetime.now().isoformat()
    
    lap = ET.SubElement(activity_elem, "Lap", StartTime=all_points[0]['time'].isoformat() if all_points else datetime.now().isoformat())
    total_time = ET.SubElement(lap, "TotalTimeSeconds")
    total_time.text = str(act1.elapsed_time + act2.elapsed_time)
    distance_elem = ET.SubElement(lap, "DistanceMeters")
    distance_elem.text = str(float(act1.distance) + float(act2.distance))
    
    track = ET.SubElement(lap, "Track")
    for point in all_points:
        tp = ET.SubElement(track, "Trackpoint")
        time_elem = ET.SubElement(tp, "Time")
        time_elem.text = point['time'].isoformat()
        if point['lat'] is not None and point['lon'] is not None:
            position = ET.SubElement(tp, "Position")
            lat = ET.SubElement(position, "LatitudeDegrees")
            lat.text = str(point['lat'])
            lon = ET.SubElement(position, "LongitudeDegrees")
            lon.text = str(point['lon'])
        if point['altitude'] is not None:
            alt = ET.SubElement(tp, "AltitudeMeters")
            alt.text = str(point['altitude'])
        if point['distance'] is not None:
            dist = ET.SubElement(tp, "DistanceMeters")
            dist.text = str(point['distance'])
        if point['heartrate'] is not None:
            hrbpm = ET.SubElement(tp, "HeartRateBpm")
            value = ET.SubElement(hrbpm, "Value")
            value.text = str(point['heartrate'])
    
    tree = ET.ElementTree(root)
    tree.write(output_file, encoding='unicode', xml_declaration=True)

def upload_activity(access_token, file_path, name, description, data_type='fit'):
    url = "https://www.strava.com/api/v3/uploads"
    headers = {'Authorization': f'Bearer {access_token}'}
    data = {
        'name': name,
        'description': description,
        'trainer': 'false',
        'commute': 'false',
        'data_type': data_type
    }
    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(url, headers=headers, data=data, files=files)
    if response.status_code == 201:
        print("Activity uploaded successfully")
    else:
        print(f"Upload failed: {response.status_code} {response.text}")

def main():
    access_token, refresh_token, expires_at = get_access_token()
    client = Client(access_token=access_token, refresh_token=refresh_token, token_expires=expires_at)

    activities = list_recent_activities(client)

    if len(activities) < 2:
        print("Not enough activities in the past week.")
        return

    try:
        idx1 = int(input("Select first activity (number): ")) - 1
        idx2 = int(input("Select second activity (number): ")) - 1
    except ValueError:
        print("Invalid input")
        return

    if idx1 < 0 or idx1 >= len(activities) or idx2 < 0 or idx2 >= len(activities):
        print("Invalid selection")
        return

    act1 = activities[idx1]
    act2 = activities[idx2]

    merge_activities(client, act1.id, act2.id, 'merged.tcx')

    name = input("Enter name for merged activity: ")
    description = input("Enter description: ")

    upload_activity(access_token, 'merged.tcx', name, description, data_type='tcx')

if __name__ == "__main__":
    main()