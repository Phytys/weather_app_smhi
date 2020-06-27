## Weather app for network engineers (this prototype work for Sweden)
A Python Flask application that collect Meteorological Observations from SMHI REST API
## Purpose
Select one of your sites and get weather data from closest smhi weather-station.
## Targeted for
- Mobile Network Engineers that use weather data as part of faultfinding. (E.g. where heavy rain and strong winds could correlate with network faults)
- Other tools: so that weather data could be automatically collected for all sites in network.

## Usage
1.	Add your list of sites in “sites/mysites.csv”
2.	Update list of sites used by autocomplete function in “templates/get_weather_data.html” 
3.	Run weather_app.py
4.	Open local host http://localhost:5000/
a.	Or serve using e.g. waitress
5.	You are good to go.

![GitHub Logo](/images/logo.png)
Format: ![Alt Text](url)

