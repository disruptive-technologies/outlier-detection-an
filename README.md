# Outlier Detection

This repository contains the example code talked about in [this application note](https://developer.disruptive-technologies.com/docs/other/application-notes/outlier-detection-on-multiple-temperature-datastreams), implementing a method of detecting outliers in multiple Disruptive Technologies (DT) Wireless Temperature Sensor timeseries using DBSCAN clustering. Written in Python 3, it uses the DT Python API to communicate with a DT Studio project and its sensors. 

## Before Running Any code
A DT Studio project containing temperature sensors should be made. Sensors with the label 'outlier_detection' will be fetched by the example code.

## Environment Setup
Dependencies can be installed using pip.
```
pip3 install -r requirements.txt
```

Using your authentication details, set the following environment variables. Information about setting up your project for API authentication can be found in this [streaming API guide](https://support.disruptive-technologies.com/hc/en-us/articles/360012377939-Using-the-stream-API).
```python
export DT_SERVICE_ACCOUNT_KEY_ID='<YOUR_SERVICE_ACCOUNT_KEY_ID>'
export DT_SERVICE_ACCOUNT_SECRET='<YOUR_SERVICE_ACCOUNT_SECRET>'
export DT_SERVICE_ACCOUNT_EMAIL='<YOUR_SERVICE_ACCOUNT_EMAIL>'
```

## Usage
Provide a Project ID to fetch data from all labeled temperature devices.

```python
python3 main.py <PROJECT_ID>
```

Use the `-h` flag to print additional flags available.
