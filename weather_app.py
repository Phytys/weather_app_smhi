import numpy as np
import pandas as pd
import json
import requests
from string import Template
import csv
import os
from flask import Flask, request, render_template
from datetime import datetime, timedelta
from flask_googlemaps import GoogleMaps
from flask_googlemaps import Map, icons
import io
import base64
from math import cos, asin, sqrt
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from waitress import serve

# Content: 1 Functions, 2 Site-list, 3 Flask app


########### 1 NOTE Functions ######################


def smhi_parameters():
    """ From smhi - get all available weather-parameters to choose between 
        E.g. Byvind_max, 1 g�ng/tim
        Returns a pandas df ['Key', 'Title', 'Summary']
    """
    smhi_version = "latest"
    smhi_ext = "json"

    parameters = {"version": smhi_version,
                  "ext": smhi_ext}

    url_entry_point = "https://opendata-download-metobs.smhi.se/api"
    url_template_full = Template(
        "/version/${version}.${ext}")
    url_smhi_api = url_entry_point + url_template_full.substitute(parameters)
    response = requests.get(url_smhi_api)
    content = response.content
    info = json.loads(content)
    smhi_parameters_dict = {}

    for t in (info["resource"]):
        # iterate over all parameters
        smhi_parameters_dict.update({t["key"]: [t["title"], t["summary"]]})

    smhi_parameters_df = pd.DataFrame.from_dict(
        smhi_parameters_dict, orient="index")
    smhi_parameters_df.reset_index(inplace=True)
    smhi_parameters_df.columns = ["Key", "Title", "Summary"]
    smhi_parameters_df["TitleSummary"] = smhi_parameters_df["Title"] + \
        ", " + smhi_parameters_df["Summary"]

    return smhi_parameters_df


def smhi_stations(smhi_parameter):
    """ From smhi - get available weather stations
    parameter:
    1. smhi_parameter: the weathter parameter to find available stations for
    Returns a pandas df  ['Key', 'Station_Name', 'lat', 'lng', 'infobox', 'icon']
    """
    smhi_version = "latest"
    smhi_ext = "json"

    parameters = {"version": smhi_version, "parameter": smhi_parameter,
                  "ext": smhi_ext}
    url_entry_point = "https://opendata-download-metobs.smhi.se/api"
    url_template_full = Template(
        "/version/${version}/parameter/${parameter}.${ext}")
    url_smhi_api = url_entry_point + url_template_full.substitute(parameters)
    response = requests.get(url_smhi_api)
    # print(response.url)
    content = response.content
    # converting to dict
    info = json.loads(content)

    smhi_stations_dict = {}

    for t in info["station"]:
        # iterate over all stations
        smhi_stations_dict.update(
            {t["key"]: [t["name"], t["latitude"], t["longitude"]]})

    smhi_stations_df = pd.DataFrame.from_dict(
        smhi_stations_dict, orient="index")
    smhi_stations_df.reset_index(inplace=True)
    smhi_stations_df.columns = ["Key", "Station_Name", "lat", "lng"]
    smhi_stations_df.index = smhi_stations_df.index.astype(int)
    smhi_stations_df.sort_index(axis=0, inplace=True)
    smhi_stations_df["infobox"] = smhi_stations_df["Key"] + \
        "_" + smhi_stations_df["Station_Name"]
    smhi_stations_df["icon"] = "http://maps.google.com/mapfiles/ms/icons/blue-dot.png"

    return smhi_stations_df


def smhi_api_request(smhi_parameter, smhi_station, smhi_period):
    
    """ From smhi - get weather data
        parameters:
        1. smhi_parameter: selected the weathter parameter (int)
        2. smhi_station: selected weathter station (int)
        3. smhi_period: Valid values are "latest-hour", "latest-day", "latest-months"
        returns a pandas df ["Date", "Value"]
    """
    smhi_version = "latest"
    smhi_ext = "json"
    parameters = {"version": smhi_version, "parameter": smhi_parameter,
                  "station": smhi_station, "period": smhi_period,
                  "ext": smhi_ext}

    url_entry_point = "https://opendata-download-metobs.smhi.se/api"
    url_template_full = Template(
        "/version/${version}/parameter/${parameter}/station/${station}/period/${period}/data.${ext}")
    url_smhi_api = url_entry_point + url_template_full.substitute(parameters)
    response = requests.get(url_smhi_api)
    # print(response.url)
    if response:    
        content = response.content
        info = json.loads(content)
        smhi_data = {}
        try:
            for t in info["value"]:
                # iterate to get date and value
                smhi_data.update({t["date"]: t["value"]})
            
            smhi_data_df = pd.DataFrame.from_dict(smhi_data, orient="index")
            smhi_data_df.reset_index(inplace=True)
            smhi_data_df.columns = ["Date", "Value"]
            smhi_data_df["Value"] = smhi_data_df["Value"].astype(float).round()
            smhi_data_df["Date"] = pd.to_datetime(smhi_data_df["Date"], unit="ms")
            smhi_data_df["Station_Key"] = smhi_station
            smhi_data_df["Parameter_Key"] = smhi_parameter
            return smhi_data_df
            
        except:
            return "No data found"

    else:
        return "No data found"
    

def distance(lat1, lon1, lat2, lon2):
    """Calculate distance beween two points
    Input latitude and longitude for the two points
    return distance
    """
    p = 0.017453292519943295
    a = 0.5 - cos((lat2-lat1)*p)/2 + cos(lat1*p)*cos(lat2*p) * (1-cos((lon2-lon1)*p)) / 2
    dist = 12742 * asin(sqrt(a))
    return dist


def closest(site, weather_param, period):
    """ Finds the closest weather station and return weather data.
        parameters:
        1. site, dict that incl lat, lng keys
        2. weather_param: selected SMHI weathter parameter key (int)
        3. period: Valid values are "latest-hour", "latest-day", "latest-months"
        return:
        1. closest weather station, {dict}
        2. the distance to closest weather station (float)
        3. weather data, a pandas df ["Date", "Value"]
        4. list of stations that were asked for data [list]
    """
    # Get a dict of available stations
    available_smhi_stations = smhi_stations(weather_param)
    available_smhi_stations = available_smhi_stations.to_dict("records")
    # initiate variables
    closest_location = {"Key":"start"}
    asked_stations = []

    # loop until 'closest weather station' with data is found. Variable weather shall be a dataframe and not a str.
    for _ in range(50):
        available_smhi_stations = [i for i in available_smhi_stations if not (i["Key"] == closest_location["Key"])]

        closest_location = min(available_smhi_stations, key=lambda p: distance(site['lat'],site['lng'],p['lat'],p['lng']))
        asked_stations.append(closest_location["Station_Name"])
        dist_station = distance(site['lat'],site['lng'],closest_location['lat'],closest_location['lng'])
        # API request data
        weather_data = smhi_api_request(weather_param, closest_location["Key"], period)
        
        if type(weather_data) != str: 
            return closest_location, dist_station, weather_data, asked_stations
    
    # if no weather data can't be found... return default values below
    closest_location = "N/A"
    dist_station = 0
    weather_data = "N/A"
    asked_stations = "N/A"
    return closest_location, dist_station, weather_data, asked_stations

# build a simple graph in matplotlib
def build_graph(x, x_label, y1, y1_label, title):
    img = io.BytesIO()
    ax = plt.gca()
    fig, ax = plt.subplots(figsize=(12,6))
    plt.plot(x, y1)
    plt.title(title)
    plt.rcParams["figure.figsize"] = (8,5)
    plt.MaxNLocator(5)
    plt.ylabel(y1_label)
    plt.xlabel(x_label)
    # rotate and align the tick labels so they look better
    fig.autofmt_xdate()
    # use a more precise date string for the x axis locations in the
    ax.fmt_xdata = mdates.DateFormatter('%Y-%m-%d')

    plt.savefig(img, format='png')
    img.seek(0)
    graph_url = base64.b64encode(img.getvalue()).decode()
    plt.close()

    return 'data:image/png;base64,{}'.format(graph_url)


########### 2 NOTE Global objects ######################

# import list of locations. Contains sites and coordinates.
sites_coord = pd.read_excel("sites/my_sites.xlsx")


########### 3 NOTE FLASK APP ######################
# initialize Flask application
app = Flask(__name__)
GoogleMaps(app)


@app.route('/')
def home():

    return(render_template('home.html'))


@app.route("/get_weather_data", methods=['GET', 'POST'])
def get_weather_data():
    # get all available weather parameters
    smhi_weather_parameters = smhi_parameters()

    if request.method == 'POST':
        site_id = request.form["site_id"]
        weather_parameter_text = request.form["weather_parameter_text"]
        period = request.form["period"]

        site = sites_coord.loc[sites_coord["site"]
                               == site_id].to_dict("records")[0]

        weather_parameter = smhi_weather_parameters.loc[smhi_weather_parameters["TitleSummary"].str.contains(
            weather_parameter_text), "Key"]
        weather_parameter = int(weather_parameter)

        # call function to get closest station and fetch data from SMHI API
        closest_smhi_station, dist_station, weather_data, asked_stations = closest(
            site, weather_parameter, period)

        # If weather_data is a string, there is no data to show
        if type(weather_data) != str:
            # build graph
            if period == "latest-months":
                x = weather_data["Date"].iloc[100:]
                y1 = weather_data["Value"].iloc[100:]
                graph_title = "Parameter: {prm} and period: {per}".format(prm= weather_parameter_text, per=period) 
            else:
                x = weather_data["Date"]
                y1 = weather_data["Value"]

            graph_title = "Parameter: {prm} and period: {per}".format(prm= weather_parameter_text, per=period)    
            x_label = "Time"
            y1_label = "Value"
            # Call function to build graph
            graph1_url = build_graph(x, x_label, y1, y1_label, graph_title)

            # Fill placeholders with information
            stations_asked = "Following weather stations were asked for data: " + str(asked_stations)
            station = "Closest weather station with data: " + \
                closest_smhi_station["Station_Name"]
            distance_to_station = "Distance to weather station: " + \
                str(round(dist_station)) + " Km"

            # Before rendering weather table, sort newes data on top
            weather_data.sort_values(by="Date", ascending=False, inplace=True)

            return render_template('weather_data_returned.html', site=site_id, st_asked=stations_asked ,
                                   prm=weather_parameter_text, stn=station,
                                   dst=distance_to_station, graph1=graph1_url,
                                   tables1=[weather_data.to_html(classes='data_frame', header=True, index=False)])
        else:
            return "No data available"

    return render_template('get_weather_data.html')


@app.route('/parameters',  methods=['GET', 'POST'])
def weather_parameters():
    pd.set_option('display.max_colwidth', 200)

    # call function to get available weather parameters from smhi api
    parameters = smhi_parameters()

    return render_template('parameters.html',  tables=[parameters.to_html(classes='data_frame', header="true", max_rows=200, index=False)])


@app.route("/stations", methods=['GET', 'POST'])
def stations():

    if request.method == 'POST':

        PARAMETER = request.form["parameter"]  # from html form
        stations = smhi_stations(PARAMETER)
        stations.drop(["infobox", "icon"], axis=1, inplace=True)

        parameter_descr = smhi_parameters()
        parameter_descr = parameter_descr.loc[parameter_descr["Key"] == PARAMETER]

        return render_template('stations_returned.html', tables1=[parameter_descr.to_html(classes='data_frame', header="true", max_rows=500, index=False)], tables2=[stations.to_html(classes='data_frame', header="true", max_rows=500, index=False)])

    return render_template('stations.html')


@app.route("/mapview", methods=['GET', 'POST'])
def mapview():
    stations = smhi_stations(smhi_parameter=21)
    stations = stations.drop(["Key", "Station_Name"], axis=1)
    stations_dict = stations.to_dict("records")

    if request.method == 'POST':

        PARAMETER = request.form["parameter"]  # from html form
        stations = smhi_stations(PARAMETER)
        stations = stations.drop(["Key", "Station_Name"], axis=1)
        stations_dict = stations.to_dict("records")

        parameter_descr = smhi_parameters()
        parameter_descr = parameter_descr.loc[parameter_descr["Key"] == PARAMETER]

        sndmap = Map(
            identifier="sndmap",
            lat=55.6658722,
            lng=12.574319,
            zoom=7,
            style="height:800px;width:1000px;margin:0;",
            markers=stations_dict
        )

        return render_template('map_returned.html', mymap=sndmap, sndmap=sndmap, tables=[parameter_descr.to_html(classes='data_frame', header="true", max_rows=200, index=False)])

    sndmap = Map(
        identifier="sndmap",
        lat=55.6658722,
        lng=12.574319,
        zoom=7,
        style="height:800px;width:1000px;margin:0;",
        markers=stations_dict
    )

    return render_template('map.html', mymap=sndmap, sndmap=sndmap)


if __name__ == "__main__":
    print(("* Loading and starting server..."
           "please wait until server has fully started"))
    app.run(debug=True)
    # replace with below code to run using waitress web server
    # serve(app, host='0.0.0.0', port=8080, threads = 6)

