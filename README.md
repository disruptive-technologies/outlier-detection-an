# Outlier Detection on Multiple Temperature Datastreams

## What am I?
This repository contains the example code talked about in [this application note (TBA)](https://support.disruptive-technologies.com/), presenting a method of detecting outliers in multiple Disruptive Technologies (DT) Wireless Temperature Sensor timeseries using DBSCAN clustering. Written in Python 3, it uses the DT Developer API to communicate with a DT Studio project and its sensors. 

## Before Running Any code
A DT Studio project containing temperature sensors should be made. Sensors with the label 'outlier_detection' will be fetched by the example code.

## Environment Setup
Dependencies can be installed using pip.
```
pip3 install -r requirements.txt
```

Edit *sensor_stream.py* to provide the following authentication details of your project. Information about setting up your project for API authentication can be found in this [streaming API guide](https://support.disruptive-technologies.com/hc/en-us/articles/360012377939-Using-the-stream-API).
```python
USERNAME   = "SERVICE_ACCOUNT_KEY"       # this is the key
PASSWORD   = "SERVICE_ACCOUT_SECRET"     # this is the secret
PROJECT_ID = "PROJECT_ID"                # this is the project id
```

## Usage
Running *python3 sensor_stream.py* without any arguments will start listening for events in the stream. When enough data has been received, outlier detection will occur on the most recent data windows. By including one or several additional arguments, more functions such as fetching historic data can be invoked.
```
usage: sensor_stream.py [-h] [--starttime] [--endtime] [--timestep] [--window]
                        [--no-plot]

Outlier detection for multistream temperature data.

optional arguments:
  -h, --help    show this help message and exit
  --starttime   Event history UTC starttime [YYYY-MM-DDTHH:MM:SSZ].
  --endtime     Event history UTC endtime [YYYY-MM-DDTHH:MM:SSZ].
  --timestep    Time in seconds between clusterings.
  --window      Seconds of data in clustering data window.
  --no-plot     Suppress streaming plot.
```

Note: When using the *--starttime* argument for a date far back in time, if many sensors exist in the project, the paging process might take several minutes.

