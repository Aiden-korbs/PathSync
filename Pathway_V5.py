import json
import re
import argparse
import time
from datetime import datetime, timedelta
import math
from itertools import combinations

# Import the library for reverse geocoding
try:
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
except ImportError:
    print("Error: 'geopy' library not found. Please run 'pip install geopy' to use the location lookup feature.")
    exit()

def get_location_name(latitude, longitude):
    """
    Performs a reverse geocode lookup with retries and a longer timeout.
    """
    geolocator = Nominatim(user_agent="nexus_point_analyzer_v2", timeout=10)
    attempts = 3
    for attempt in range(attempts):
        try:
            # Adding a 1-second delay to respect Nominatim's usage policy
            time.sleep(1) 
            location = geolocator.reverse((latitude, longitude), exactly_one=True, language='en')
            return location.address if location else "Unknown Location"
        except (GeocoderTimedOut, GeocoderUnavailable):
            if attempt < attempts - 1:
                print(f"  Location service timed out, retrying ({attempt + 2}/{attempts})...")
                time.sleep(2) # Wait 2 seconds before retrying
            else:
                return "Location service timed out or is unavailable."
        except Exception as e:
            return f"An error occurred during location lookup: {e}"

def load_json_file(file_path):
    """Loads a JSON file from the given path and returns its content."""
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
    Parses various timeline JSON structures and returns a standardized list of events,
    filtered by the given year range.
    """
    events = []

    def event_in_range(dt):
        if start_year and dt.year < start_year: return False
        if end_year and dt.year > end_year: return False
        return True

    if isinstance(json_data, dict) and 'semanticSegments' in json_data:
        for segment in json_data.get('semanticSegments', []):
            if 'timelinePath' in segment:
                for point in segment.get('timelinePath', []):
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

    return sorted(events, key=lambda x: x['timestamp'])

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points on the earth."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return c * 6371 # Radius of earth in kilometers.

def compare_timelines(data1, data2, time_threshold_minutes=2, distance_threshold_km=0.1):
    """Compares two sorted timelines to find events that occurred close in time and space."""
    matches = []
    time_threshold = timedelta(minutes=time_threshold_minutes)
    i, j = 0, 0

    while i < len(data1) and j < len(data2):
        event1 = data1[i]
        time_difference = event1['timestamp'] - data2[j]['timestamp']

        if time_difference > time_threshold: j += 1; continue
        if time_difference < -time_threshold: i += 1; continue

        k = j
        while k < len(data2):
            event2 = data2[k]
            sub_time_diff = abs(event1['timestamp'] - event2['timestamp'])
            if sub_time_diff > time_threshold: break
            
            distance = haversine_distance(event1['latitude'], event1['longitude'], event2['latitude'], event2['longitude'])
            if distance <= distance_threshold_km:
                matches.append({'event1': event1, 'event2': event2, 'time_difference': sub_time_diff, 'distance_km': distance})
            k += 1
        i += 1
    return matches

def find_closest_match(matches):
    """Finds the single best match from a list of matches based on distance."""
    return min(matches, key=lambda x: x['distance_km']) if matches else None

def main():
    """Main function to execute the timeline comparison script."""
    parser = argparse.ArgumentParser(
        description="Nexus Point: Compares timeline JSON files to find proximity events.",
        epilog="Example: python3 nexus_point.py Aiden.json Kate.json --start-year 2022"
    )
    parser.add_argument("files", nargs='+', help="The list of JSON timeline files to process.")
    parser.add_argument("--time", type=int, default=2, help="Time threshold in MINUTES for a match (default: 2).")
    parser.add_argument("--distance", type=float, default=100, help="Distance threshold in METERS for a match (default: 100).")
    parser.add_argument("--start-year", type=int, help="The starting year for the analysis.")
    parser.add_argument("--end-year", type=int, help="The ending year for the analysis.")
    
    args = parser.parse_args()
    start_time = time.time()
    
    processed_data = {}
    for file_path in args.files:
        raw_data = load_json_file(file_path)
        if raw_data:
            events = parse_timeline_data(raw_data, args.start_year, args.end_year)
            if events:
                processed_data[file_path] = events
                print(f"Successfully processed {file_path}, found {len(events)} events.")
            else:
                print(f"Warning: No valid events found in {file_path} for the specified year range.")

    if len(processed_data) < 2:
        print("Need at least two valid timeline files to compare. Exiting.")
        return

    total_matches = 0
    overall_closest_match = None

    for (file1, data1), (file2, data2) in combinations(processed_data.items(), 2):
        print(f"\n--- Comparing {file1} and {file2} ---")
        matches = compare_timelines(data1, data2, args.time, args.distance / 1000)
        
        if matches:
            total_matches += len(matches)
            print(f"Found {len(matches)} matches.")
            
            closest_pair_match = find_closest_match(matches)
            if closest_pair_match:
                print(f"  Closest Match in this pair: Distance: {closest_pair_match['distance_km'] * 1000:.2f} meters")
                
                if overall_closest_match is None or closest_pair_match['distance_km'] < overall_closest_match['distance_km']:
                    overall_closest_match = closest_pair_match
                    overall_closest_match['files'] = (file1, file2)
        else:
            print("No matches found.")

    print("\n--- Overall Results ---")
    print(f"Total matches found across all files: {total_matches}")

    if overall_closest_match:
        files = overall_closest_match['files']
        event1 = overall_closest_match['event1']
        event2 = overall_closest_match['event2']
        
        print("\nLooking up location of closest match...")
        location_name = get_location_name(event1['latitude'], event1['longitude'])
        
        print(f"\nThe absolute closest match was between '{files[0]}' and '{files[1]}':")
        print(f"  Location Name: {location_name}")
        print(f"  Distance: {overall_closest_match['distance_km'] * 1000:.2f} meters")
        print(f"  Time Difference: {overall_closest_match['time_difference'].total_seconds():.2f} seconds")
        print(f"  - {files[0]} Location: Lat {event1['latitude']}, Lon {event1['longitude']}")
        print(f"    - Timestamp: {event1['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  - {files[1]} Location: Lat {event2['latitude']}, Lon {event2['longitude']}")
        print(f"    - Timestamp: {event2['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")

    execution_time = time.time() - start_time
    print(f"\nTotal Execution Time: {execution_time:.2f} seconds")

if __name__ == '__main__':
    main()