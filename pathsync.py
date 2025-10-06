import json
import re
import argparse
import time
from datetime import datetime, timedelta, timezone
import math
from itertools import combinations

# Import libraries for timezone conversion
try:
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
    from timezonefinder import TimezoneFinder
    import pytz
except ImportError:
    print("Error: Required libraries not found. Please run:")
    print("python3 -m pip install geopy timezonefinder pytz")
    exit()

def get_location_name(latitude, longitude):
    """Performs a reverse geocode lookup with retries."""
    geolocator = Nominatim(user_agent="nexus_point_analyzer_v4", timeout=10)
    for attempt in range(3):
        try:
            time.sleep(1)
            location = geolocator.reverse((latitude, longitude), exactly_one=True, language='en')
            return location.address if location else "Unknown Location"
        except (GeocoderTimedOut, GeocoderUnavailable):
            if attempt < 2:
                print(f"  Location service timed out, retrying ({attempt + 2}/3)...")
                time.sleep(2)
            else:
                return "Location service timed out or is unavailable."
        except Exception:
            return "Could not determine location name."

def get_local_time(utc_dt, lat, lon):
    """Converts a UTC datetime to the local time at the given coordinates."""
    try:
        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lng=lon, lat=lat)
        if tz_name:
            local_tz = pytz.timezone(tz_name)
            return utc_dt.astimezone(local_tz)
        return utc_dt # Fallback to UTC if timezone not found
    except Exception:
        return utc_dt

def load_json_file(file_path):
    """Loads a JSON file from the given path."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found at '{file_path}'. Skipping.")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{file_path}'. Skipping.")
        return None

def parse_timeline_data(json_data, start_year=None, end_year=None):
    """
    Parses various timeline JSON structures and returns a standardized list of events.
    """
    events = []

    def event_in_range(dt):
        if start_year and dt.year < start_year: return False
        if end_year and dt.year > end_year: return False
        return True

    # Handler for formats like Aiden.json, Lukas.json
    if isinstance(json_data, dict) and 'semanticSegments' in json_data:
        for segment in json_data.get('semanticSegments', []):
            path = segment.get('timelinePath', [])
            if path:
                for point in path:
                    try:
                        timestamp = datetime.fromisoformat(point.get('time'))
                        if event_in_range(timestamp):
                            coords = re.findall(r"[-+]?\d+\.\d+", point.get('point', ''))
                            if len(coords) == 2:
                                events.append({'timestamp': timestamp, 'latitude': float(coords[0]), 'longitude': float(coords[1])})
                    except (ValueError, TypeError): continue
            elif 'visit' in segment:
                 try:
                    timestamp = datetime.fromisoformat(segment.get('startTime'))
                    if event_in_range(timestamp):
                        location = segment['visit']['topCandidate'].get('placeLocation', '')
                        coords = re.findall(r"[-+]?\d+\.\d+", location)
                        if len(coords) == 2:
                            events.append({'timestamp': timestamp, 'latitude': float(coords[0]), 'longitude': float(coords[1])})
                 except (KeyError, ValueError, TypeError): continue

    # Handler for format like Kate.json
    elif isinstance(json_data, list):
        for item in json_data:
            try:
                timestamp = datetime.fromisoformat(item.get('startTime'))
                if event_in_range(timestamp):
                    location = item.get('visit', {}).get('topCandidate', {}).get('placeLocation', '')
                    coords = re.findall(r"[-+]?\d+\.\d+", location)
                    if len(coords) == 2:
                        events.append({'timestamp': timestamp, 'latitude': float(coords[0]), 'longitude': float(coords[1])})
            except (ValueError, TypeError): continue

    # Handler for format like Hana.json
    elif isinstance(json_data, dict) and 'locations' in json_data:
        for loc in json_data.get('locations', []):
            try:
                timestamp_str = loc.get('timestamp', '').replace('Z', '+00:00')
                timestamp = datetime.fromisoformat(timestamp_str)
                if event_in_range(timestamp):
                    lat = loc.get('latitudeE7') / 1e7
                    lon = loc.get('longitudeE7') / 1e7
                    events.append({'timestamp': timestamp, 'latitude': lat, 'longitude': lon})
            except (ValueError, TypeError, KeyError): continue
    
    return sorted(events, key=lambda x: x['timestamp'])

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculates distance between two coordinates."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return 2 * math.asin(math.sqrt(a)) * 6371

def compare_timelines(data1, data2, time_threshold_minutes=2, distance_threshold_km=0.1):
    """Compares two sorted timelines to find proximity events."""
    matches = []
    time_threshold = timedelta(minutes=time_threshold_minutes)
    i, j = 0, 0
    while i < len(data1) and j < len(data2):
        time_difference = data1[i]['timestamp'] - data2[j]['timestamp']
        if time_difference > time_threshold: j += 1; continue
        if time_difference < -time_threshold: i += 1; continue
        k = j
        while k < len(data2):
            event2 = data2[k]
            sub_time_diff = abs(data1[i]['timestamp'] - event2['timestamp'])
            if sub_time_diff > time_threshold: break
            distance = haversine_distance(data1[i]['latitude'], data1[i]['longitude'], event2['latitude'], event2['longitude'])
            if distance <= distance_threshold_km:
                matches.append({'event1': data1[i], 'event2': event2, 'time_difference': sub_time_diff, 'distance_km': distance})
            k += 1
        i += 1
    return matches

def find_closest_match(matches):
    """Finds the single best match from a list."""
    return min(matches, key=lambda x: x['distance_km']) if matches else None

def main():
    """Main function to execute the script."""
    parser = argparse.ArgumentParser(description="Nexus Point: Compares timeline JSON files to find proximity events.")
    parser.add_argument("files", nargs='+', help="List of JSON timeline files.")
    parser.add_argument("--time", type=int, default=2, help="Time threshold in MINUTES (default: 2).")
    parser.add_argument("--distance", type=float, default=100, help="Distance threshold in METERS (default: 100).")
    parser.add_argument("--start-year", type=int, help="Starting year for analysis.")
    parser.add_argument("--end-year", type=int, help="Ending year for analysis.")
    args = parser.parse_args()
    
    start_time = time.time()
    processed_data = {}
    for file_path in args.files:
        raw_data = load_json_file(file_path)
        if raw_data:
            events = parse_timeline_data(raw_data, args.start_year, args.end_year)
            if events:
                print(f"Successfully processed {file_path}, found {len(events)} events.")
                processed_data[file_path] = events
            else:
                print(f"Warning: No valid events found in {file_path} for the specified year range.")
    
    if len(processed_data) < 2:
        print("Need at least two valid timeline files to compare. Exiting.")
        return

    total_matches, overall_closest_match = 0, None
    for (file1, data1), (file2, data2) in combinations(processed_data.items(), 2):
        print(f"\n--- Comparing {file1} and {file2} ---")
        matches = compare_timelines(data1, data2, args.time, args.distance / 1000)
        if matches:
            total_matches += len(matches)
            closest_pair_match = find_closest_match(matches)
            print(f"Found {len(matches)} matches. Closest match in this pair: {closest_pair_match['distance_km'] * 1000:.2f} meters.")
            if overall_closest_match is None or closest_pair_match['distance_km'] < overall_closest_match['distance_km']:
                overall_closest_match = closest_pair_match
                overall_closest_match['files'] = (file1, file2)
        else:
            print("No matches found.")

    print(f"\n--- Overall Results ---\nTotal matches found across all files: {total_matches}")
    if overall_closest_match:
        event1, event2 = overall_closest_match['event1'], overall_closest_match['event2']
        files = overall_closest_match['files']
        
        # Convert to UTC first to ensure a correct base for local conversion
        event1_ts_utc = event1['timestamp'].astimezone(timezone.utc)
        event2_ts_utc = event2['timestamp'].astimezone(timezone.utc)

        # Convert to the timezone of the actual location
        event1_ts_local = get_local_time(event1_ts_utc, event1['latitude'], event1['longitude'])
        event2_ts_local = get_local_time(event2_ts_utc, event2['latitude'], event2['longitude'])
        
        print("\nLooking up location of closest match...")
        location_name = get_location_name(event1['latitude'], event1['longitude'])
        
        print(f"\nThe absolute closest match was between '{files[0]}' and '{files[1]}':")
        print(f"  Location Name: {location_name}")
        print(f"  Distance: {overall_closest_match['distance_km'] * 1000:.2f} meters")
        print(f"  Time Difference: {overall_closest_match['time_difference'].total_seconds():.2f} seconds")
        print(f"  - {files[0]} Location: Lat {event1['latitude']}, Lon {event1['longitude']}")
        print(f"    - Timestamp: {event1_ts_local.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
        print(f"  - {files[1]} Location: Lat {event2['latitude']}, Lon {event2['longitude']}")
        print(f"    - Timestamp: {event2_ts_local.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")

    print(f"\nTotal Execution Time: {time.time() - start_time:.2f} seconds")

if __name__ == '__main__':
    main()
