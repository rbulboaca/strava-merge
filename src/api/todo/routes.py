from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from starlette.requests import Request
import requests
from stravalib import Client
import xml.etree.ElementTree as ET

from .models import Activity, MergeRequest, UserToken, Settings

settings = Settings()

router = APIRouter(prefix="/api")

async def get_strava_client(user_id: str = "user1"):  # For simplicity, fixed user
    token = await UserToken.find_one(UserToken.user_id == user_id)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    client = Client(access_token=token.access_token, refresh_token=token.refresh_token, token_expires=token.expires_at)
    return client

@router.get("/auth/url")
async def get_auth_url():
    client_id = settings.STRAVA_CLIENT_ID
    redirect_uri = settings.STRAVA_REDIRECT_URI or "http://localhost:3100/auth/callback"
    scope = "activity:read,activity:write"
    url = f"https://www.strava.com/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope={scope}"
    return {"url": url}

@router.get("/auth/callback")
async def auth_callback_get(code: str):
    client_id = settings.STRAVA_CLIENT_ID
    client_secret = settings.STRAVA_CLIENT_SECRET
    token_response = requests.post("https://www.strava.com/oauth/token", data={
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'grant_type': 'authorization_code'
    }).json()
    access_token = token_response['access_token']
    refresh_token = token_response['refresh_token']
    expires_at = token_response['expires_at']
    user_id = "user1"
    existing = await UserToken.find_one(UserToken.user_id == user_id)
    if existing:
        existing.access_token = access_token
        existing.refresh_token = refresh_token
        existing.expires_at = expires_at
        await existing.save()
    else:
        token_doc = UserToken(user_id=user_id, access_token=access_token, refresh_token=refresh_token, expires_at=expires_at)
        await token_doc.insert()
    return {"status": "authenticated"}

@router.get("/auth/status")
async def auth_status():
    user_id = "user1"
    token = await UserToken.find_one(UserToken.user_id == user_id)
    if token:
        return {"authenticated": True}
    return {"authenticated": False}

@router.get("/activities", response_model=List[Activity])
async def get_activities(client: Client = Depends(get_strava_client)):
    activities = client.get_activities(after=datetime.now() - timedelta(days=30))  # Last 30 days
    return [Activity(
        id=a.id,
        name=a.name,
        start_date=a.start_date.isoformat(),
        type=a.type,
        distance=float(a.distance),
        moving_time=a.moving_time,
        elapsed_time=a.elapsed_time,
        total_elevation_gain=float(a.total_elevation_gain),
        workout_type=a.workout_type,
        average_speed=float(a.average_speed),
        max_speed=float(a.max_speed),
        has_heartrate=a.has_heartrate,
        average_heartrate=a.average_heartrate,
        max_heartrate=a.max_heartrate,
        heartrate_opt_out=a.heartrate_opt_out,
        display_hide_heartrate_option=a.display_hide_heartrate_option,
        elev_high=a.elev_high,
        elev_low=a.elev_low,
        pr_count=a.pr_count,
        total_photo_count=a.total_photo_count,
        has_kudoed=a.has_kudoed
    ) for a in activities[:50]]  # Limit to 50

@router.post("/merge")
async def merge_activities(request: MergeRequest, client: Client = Depends(get_strava_client)):
    if len(request.activity_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 activities required")
    
    # Get all activities
    activities = []
    all_streams = []
    for activity_id in request.activity_ids:
        act = client.get_activity(activity_id)
        activities.append(act)
        streams = client.get_activity_streams(activity_id, types=['time', 'latlng', 'distance', 'altitude', 'heartrate', 'cadence', 'watts'])
        all_streams.append(streams)
    
    sport = activities[0].type  # Use sport from first activity
    
    def create_points(streams, start_time):
        points = []
        times = streams.get('time', {}).data if 'time' in streams else []
        latlngs = streams.get('latlng', {}).data if 'latlng' in streams else []
        distances = streams.get('distance', {}).data if 'distance' in streams else []
        altitudes = streams.get('altitude', {}).data if 'altitude' in streams else []
        heartrates = streams.get('heartrate', {}).data if 'heartrate' in streams else []
        cadences = streams.get('cadence', {}).data if 'cadence' in streams else []
        wattss = streams.get('watts', {}).data if 'watts' in streams else []
        
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
    
    all_points = []
    cumulative_distance = 0
    for i, (act, streams) in enumerate(zip(activities, all_streams)):
        points = create_points(streams, act.start_date)
        if points:
            # Adjust distances for subsequent activities
            if i > 0:
                for p in points:
                    if p['distance'] is not None:
                        p['distance'] += cumulative_distance
            max_dist = max((p['distance'] for p in points if p['distance'] is not None), default=0)
            cumulative_distance += max_dist
        all_points.extend(points)
    
    all_points.sort(key=lambda p: p['time'])
    
    # Create TCX
    root = ET.Element("TrainingCenterDatabase", xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2")
    activities_elem = ET.SubElement(root, "Activities")
    activity_elem = ET.SubElement(activities_elem, "Activity", Sport=sport)
    id_elem = ET.SubElement(activity_elem, "Id")
    id_elem.text = datetime.now().isoformat()
    
    total_time = sum(act.elapsed_time for act in activities)
    total_distance = sum(float(act.distance) for act in activities)
    
    lap = ET.SubElement(activity_elem, "Lap", StartTime=all_points[0]['time'].isoformat() if all_points else datetime.now().isoformat())
    total_time_elem = ET.SubElement(lap, "TotalTimeSeconds")
    total_time_elem.text = str(total_time)
    distance_elem = ET.SubElement(lap, "DistanceMeters")
    distance_elem.text = str(total_distance)
    
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
    tcx_content = ET.tostring(root, encoding='unicode', xml_declaration=True)
    
    # Upload to Strava
    upload_url = "https://www.strava.com/api/v3/uploads"
    headers = {'Authorization': f'Bearer {client.access_token}'}
    data = {
        'name': request.name,
        'description': request.description,
        'trainer': 'false',
        'commute': 'false',
        'data_type': 'tcx'
    }
    files = {'file': ('merged.tcx', tcx_content)}
    response = requests.post(upload_url, headers=headers, data=data, files=files)
    if response.status_code == 201:
        upload_id = response.json().get('id')
        return {"message": f"Activity merged and uploaded successfully! Upload ID: {upload_id}"}
    else:
        raise HTTPException(status_code=400, detail=f"Upload failed: {response.text}")
