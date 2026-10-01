# ISS Pass Calendar

Shows when the International Space Station passes over you, and which passes you can actually
see with your own eyes. Works offline once orbit data is saved.

## Run

### macOS / Linux

In a terminal inside this folder:

```
bash run.sh
```

### Windows

Install Python 3.9 or newer from https://www.python.org/downloads/ and tick
"Add python.exe to PATH" on the first installer screen. Then double-click `run.bat`,
or run it in a terminal inside this folder:

```
run.bat
```

In PowerShell (the default terminal in VS Code on Windows) type `.\run.bat` instead.

### Both

The first start creates `.venv` and installs everything, later starts are fast.
Then open http://127.0.0.1:5001 and search for your city. Stop the app with Ctrl+C.

In VS Code: open this folder, run the start script once in the terminal (so `.venv` exists),
then press F5 and pick "ISS Pass Calendar".

### By hand

macOS / Linux:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app app run --port 5001
```

Windows (Command Prompt):

```
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
flask --app app run --port 5001
```

In Windows PowerShell, activate with `.venv\Scripts\Activate.ps1` instead. If PowerShell refuses
to run it, use Command Prompt or `run.bat`.

## Demo with the bundled sample data

`data/iss_sample_2014.tle` is a real ISS element set from 20 Jan 2014. Start the app with a
clock set to that time, pick a location, then load the file on the Offline page ("Load data from a file"):

```
ISSPASS_NOW=2014-01-21T12:00:00Z flask --app app run --port 5001     # macOS / Linux
set ISSPASS_NOW=2014-01-21T12:00:00Z && flask --app app run --port 5001   # Windows Command Prompt
```

Automatic downloads are switched off in demo mode, because today's data would look like it
comes from the future.

## Tests

```
python -m pytest -q
```

59 tests, including a cross-check of pass times against pyorbital (an independent SGP4
implementation), a check that every "visible" pass happens in a dark sky, offline place search,
and end-to-end tests with all network access blocked.

## Weather

For every pass the app looks at the forecast cloud cover for that hour (Open-Meteo, no API key needed)
and marks it as Clear (up to 25 %), Some clouds (up to 60 %) or Cloudy. The passes page shows today's
weather, and if the next visible pass is cloudy it suggests the next one with a better sky.
The forecast is saved, so the last one is still shown when there is no internet.

## Chance to see it (0 to 10)

Every visible pass gets a score. Passes that cannot be seen get 0.

1. Pass quality (0 to 1): 50 % how high it gets (10° = 0, 60° or more = 1), 30 % how long it is
   visible (5 minutes or more = 1), 20 % how dark the sky is (sun 6° below the horizon = 0, 18° = 1).
2. Base score: 4 + 6 x pass quality. Even a low, short pass is bright, so a visible pass never starts below 4.
3. Weather factor: 1 - 0.9 x cloud cover. Rain or snow multiplies it by 0.3, fog by 0.2.
   Without a forecast the factor is 1.
4. Chance = base score x weather factor, rounded and kept between 0 and 10.

If the next visible pass scores 4 or less, the app suggests a later pass with a better score.

## How "visible" is decided

A pass counts as visible when, at the same time, the station is at least 10° above the horizon,
the station is in sunlight, and the sun is more than 6° below your horizon (the sky is dark).
Only the visible part of the pass is shown, and it must last at least 30 seconds.

Town data: GeoNames (via geonamescache), about 34,000 places with more than 15,000 people.
The same place is never saved twice: anything within 10 km of a saved place counts as that place.
