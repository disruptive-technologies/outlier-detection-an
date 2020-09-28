# packages
import os
import sys
import time
import json
import argparse
import datetime
import requests
import sseclient
import matplotlib.pyplot as plt

# project
from project.sensors import Temperature
from project.sensors import Proximity
from config.sensorlist import sensorlist
from config.styling import styling_init
import project.helpers as hlp


class Director():

    def __init__(self, username='', password='', project_id='', api_url_base=''):
        # give to self
        self.username     = username
        self.password     = password
        self.project_id   = project_id
        self.api_url_base = api_url_base

        # variables
        self.last_update = -1

        # initialise plot styling
        styling_init()

        # set stream endpoint
        self.stream_endpoint = "{}/projects/{}/devices:stream".format(self.api_url_base, self.project_id)

        # parse system arguments
        self.__parse_sysargs()

        # set history- and streaming filters
        self.__set_filters()

        # fetch list of devices in project
        self.__fetch_project_devices()

        # fetch sensors
        self.__spawn_devices()


    def __parse_sysargs(self):
        """
        Parse for command line arguments.

        """

        # create parser object
        parser = argparse.ArgumentParser(description='Explanatory information here.')

        # get UTC time now
        now = (datetime.datetime.utcnow().replace(microsecond=0)).isoformat() + 'Z'

        # general arguments
        parser.add_argument('--starttime', metavar='', help='Event history UTC starttime [YYYY-MM-DDTHH:MM:SSZ].', required=False, default=now)
        parser.add_argument('--endtime',   metavar='', help='Event history UTC endtime [YYYY-MM-DDTHH:MM:SSZ].',   required=False, default=now)

        # boolean flags
        parser.add_argument('--no-plot',   action='store_true', help='Suppress streaming plot.')

        # convert to dictionary
        self.args = vars(parser.parse_args())

        # set history flag
        if now == self.args['starttime']:
            self.fetch_history = False
        else:
            self.fetch_history = True


    def __set_filters(self):
        """
        Set filters for data fetched through API.

        """

        # historic events
        self.history_params = {
            'page_size': 1000,
            'start_time': self.args['starttime'],
            'end_time': self.args['endtime'],
            'event_types': ['temperature', 'objectPresent']
        }

        # stream events
        self.stream_params = {
            'event_types': ['temperature', 'objectPresent']
        }


    def __fetch_project_devices(self):
        # request list
        devices_list_url = "{}/projects/{}/devices".format(self.api_url_base,  self.project_id)
        device_listing = requests.get(devices_list_url, auth=(self.username, self.password))
        
        # remove fluff
        if device_listing.status_code < 300:
            self.project_devices = device_listing.json()['devices']
        else:
            print(device_listing.json())
            hlp.print_error('Status Code: {}'.format(device_listing.status_code), terminate=True)


    def __spawn_devices(self):
        """
        Use list of devices to spawn a Desk- and Reference object.
        One Reference object in total and one Desk object per desk sensor.

        """

        # empty lists of devices
        self.temperatures = []
        self.proximities  = []
        self.sensor_ids   = []

        # iterate list of devices
        for device in self.project_devices:
            # get device id
            device_id = os.path.basename(device['name'])
            
            # look for device-id in sensorlist
            for sensor in sensorlist:
                if sensor['id'] == device_id:
                    # check if temperature
                    if device['type'] == 'temperature':
                        # append an initialised desk object
                        self.temperatures.append(Temperature(device, device_id, self.args))
                        self.sensor_ids.append(device_id)

                    # check if door
                    elif device['type'] == 'proximity':
                        self.proximities.append(Proximity(device, device_id, self.args))
                        self.sensor_ids.append(device_id)


    def __new_event_data(self, event_data, cout=True):
        """
        Receive new event_data json and pass it along to the correct device object.

        Parameters
        ----------
        event_data : dictionary
            Data json containing new event data.
        cout : bool
            Will print event information to console if True.

        """

        # get id of source sensor
        source_id = os.path.basename(event_data['targetName'])

        # list of fields we're looking for
        valid_fields = ['temperature', 'objectPresent']

        # verify temperature event
        if any(field in event_data['data'].keys() for field in valid_fields):
            # find sensor to related id
            for sensor in self.temperatures + self.proximities:
                if sensor.sensor_id == source_id:
                    # cout
                    if cout: print('-- New Event for {}.'.format(source_id))

                    # serve event to desk
                    sensor.new_event_data(event_data)


    def __fetch_event_history(self):
        """
        For each sensor in project, request all events since --starttime from API.

        """

        # initialise empty event list
        self.event_history = []

        # iterate devices
        for device in self.project_devices:
            # isolate device identifier
            device_id = os.path.basename(device['name'])

            # skip if not in sensorlist
            if device_id not in self.sensor_ids:
                continue
        
            # some printing
            print('-- Getting event history for {}'.format(device_id))
        
            # initialise next page token
            self.history_params['page_token'] = None
        
            # set endpoints for event history
            event_list_url = "{}/projects/{}/devices/{}/events".format(self.api_url_base, self.project_id, device_id)
        
            # perform paging
            while self.history_params['page_token'] != '':
                event_listing = requests.get(event_list_url, auth=(self.username, self.password), params=self.history_params)
                event_json = event_listing.json()

                if event_listing.status_code < 300:
                    self.history_params['page_token'] = event_json['nextPageToken']
                    self.event_history += event_json['events']
                else:
                    print(event_json)
                    hlp.print_error('Status Code: {}'.format(event_listing.status_code), terminate=True)
        
                if self.history_params['page_token'] != '':
                    print('\t-- paging')
        
        # sort event history in time
        self.event_history.sort(key=hlp.json_sort_key, reverse=False)


    def run_history(self, plot=True):
        """
        Iterate through and calculate occupancy for event history.

        """

        # do nothing if starttime not given
        if not self.fetch_history:
            return

        # get list of hsitoric events
        self.__fetch_event_history()
        
        # estimate occupancy for history 
        cc = 0
        for i, event_data in enumerate(self.event_history):
            cc = hlp.loop_progress(cc, i, len(self.event_history), 25, name='event history')

            # serve event to director
            self.__new_event_data(event_data, cout=False)

        # plot
        if not self.args['no_plot']:
            self.plot(blocking=True, show=True)


    def run_stream(self, n_reconnects=5):
        """
        Estimate occupancy on realtime stream data from sensors.

        Parameters
        ----------
        n_reconnects : int
            Number of reconnection attempts at disconnect.

        """

        # cout
        print("Listening for events... (press CTRL-C to abort)")
    
        # reinitialise plot
        if not self.args['no_plot']:
            self.plot(blocking=False)
    
        # loop indefinetly
        nth_reconnect = 0
        while nth_reconnect < n_reconnects:
            try:
                # reset reconnect counter
                nth_reconnect = 0
        
                # get response
                response = requests.get(self.stream_endpoint, auth=(self.username, self.password), headers={'accept':'text/event-stream'}, stream=True, params=self.stream_params)
                client = sseclient.SSEClient(response)
        
                # listen for events
                print('Connected.')
                for event in client.events():
                    # new data received
                    event_data = json.loads(event.data)['result']['event']
        
                    # serve event to director
                    self.__new_event_data(event_data)
        
                    # plot progress
                    if not self.args['no_plot']:
                        self.plot(blocking=False)
            
            # catch errors
            # Note: Some VPNs seem to cause quite a lot of packet corruption (?)
            except requests.exceptions.ConnectionError:
                nth_reconnect += 1
                print('Connection lost, reconnection attempt {}/{}'.format(nth_reconnect, n_reconnects))
            except requests.exceptions.ChunkedEncodingError:
                nth_reconnect += 1
                print('An error occured, reconnection attempt {}/{}'.format(nth_reconnect, n_reconnects))
            except KeyError:
                print('Error in event package. Skipping...')
                print(event_data)
                print()
            
            # wait 1s before attempting to reconnect
            time.sleep(1)


    def initialise_plot(self):
        self.fig, self.ax = plt.subplots()


    def plot(self, blocking=True, show=True):
        # initialise if not open
        if not hasattr(self, 'ax') or not plt.fignum_exists(self.fig.number):
            self.initialise_plot()

        # refresh plot
        self.ax.cla()

        # draw sensor data
        for sensor in self.temperatures + self.proximities:
            self.ax.plot(sensor.get_timestamps(), sensor.get_values(), label=sensor.sensor_id)

        if blocking:
            if show:
                plt.show()
            else:
                plt.waitforbuttonpress()
        else:
            plt.pause(0.01)

