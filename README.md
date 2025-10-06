# PathSync
PathSync: Timeline Proximity Analyzer
PathSync is a powerful command-line tool designed to analyze and compare multiple Google Timeline JSON exports to discover "proximity events"—instances where individuals were at the same place at nearly the same time.

It intelligently parses different Google Takeout formats, calculates distances, and performs reverse geocoding to identify the real-world location of the closest encounter, all while correctly handling complex timezone conversions.

Key Features
Multi-File Comparison: Compares two or more timeline files simultaneously to find matches between all pairs.

Multi-Format Support: Automatically parses several known Google Timeline JSON structures, including older and newer formats.

Date Filtering: Narrow your analysis to a specific period using start and end year arguments.

Adjustable Thresholds: Customize the time (minutes) and distance (meters) thresholds to define what constitutes a "match."

Closest Match Identification: Pinpoints the single closest event across all comparisons based on distance.

Reverse Geocoding: Looks up the physical address of the closest match to provide real-world context.

Location-Aware Timezones: Automatically converts and displays timestamps in the correct local timezone of where the event occurred.

Optimized Performance: Uses an efficient two-pointer algorithm to quickly compare large timeline files without a significant performance hit.

How It Works
The script processes each JSON file, regardless of its internal structure, and extracts a standardized list of timestamped coordinate events. These lists are then sorted chronologically.

Using an optimized two-pointer algorithm, it iterates through the timelines simultaneously, identifying all events that fall within the user-defined time and distance thresholds. The Haversine formula is used to accurately calculate the great-circle distance between coordinates.

Finally, for the single closest match found, the script uses the geopy library to find the physical address and the timezonefinder library to display the event timestamps in their correct local time.

Prerequisites
Python 3.x

The following Python libraries: geopy, timezonefinder, and pytz.

Your Google Timeline JSON export files.

Getting Your Data
You can download your location history from Google Takeout.

Visit the Google Takeout page and click "Deselect all."

Scroll down and select "Location History."

Ensure the format is set to JSON.

Proceed to create and download your export.

Installation
Clone the repository or download the script.

Install the required Python libraries by running the following command in your terminal:

python3 -m pip install geopy timezonefinder pytz

Usage
Run the script from your terminal, providing the paths to your JSON files as arguments.

Basic Examples
Compare two timeline files:

python3 pathsync.py file1.json file2.json

Compare three timeline files:

python3 pathsync.py file1.json file2.json file3.json

Advanced Examples
Filter for events that occurred in the year 2023:

python3 pathsync.py file1.json file2.json --start-year 2023 --end-year 2023

Find matches within a 5-minute and 50-meter threshold:

python3 pathsync.py file1.json file2.json --time 5 --distance 50

Command-Line Arguments
Argument

Description

Default

Example

files

(Required) One or more JSON timeline files to compare.

-

file1.json file2.json

--time

The time difference in minutes to consider a match.

2

--time 5

--distance

The distance in meters to consider a match.

100

--distance 50

--start-year

The year to start the analysis from.

-

--start-year 2022

--end-year

The year to end the analysis at.

-

--end-year 2023

Sample Output
Successfully processed Timeline1.json, found 57378 events.
Successfully processed Timeline2.json, found 7023 events.
Successfully processed Timeline3.json, found 95120 events.

--- Comparing Timeline1.json and Timeline2.json ---
Found 78 matches. Closest match in this pair: 5.85 meters.

--- Comparing Timeline1.json and Timeline3.json ---
No matches found.

--- Comparing Timeline2.json and Timeline3.json ---
Found 152 matches. Closest match in this pair: 3.12 meters.

--- Overall Results ---
Total matches found across all files: 230

Looking up location of closest match...

The absolute closest match was between 'Timeline2.json' and 'Timeline3.json':
  Location Name: Indooroopilly Shopping Centre, 180, Moggill Road, Indooroopilly, Brisbane, Queensland, 4068, Australia
  Distance: 3.12 meters
  Time Difference: 45.18 seconds
  - Timeline2.json Location: Lat -27.493355, Lon 152.975876
    - Timestamp: 2023-11-06 12:52:31 AEST+1000
  - Timeline3.json Location: Lat -27.493372, Lon 152.975853
    - Timestamp: 2023-11-06 12:53:16 AEST+1000

Total Execution Time: 12.45 seconds

License
This project is licensed under the MIT License.
