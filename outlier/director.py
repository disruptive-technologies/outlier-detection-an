# packages
import os
import time
import json
import argparse
import datetime
import requests
import sseclient
import numpy             as np
import matplotlib.pyplot as plt
from sklearn.cluster   import DBSCAN
from scipy.interpolate import interp1d

# project
from outlier.sensors import Temperature
import outlier.helpers   as hlp
import config.parameters as prm
import config.styling    as stl


class Director():
    """
    Handles all API interfacing, including fetching sensors list and updating them.
    Creates one Sensor object per temperature sensor in scheme.
    When new event data arrives in stream, delegate to the correct sensor for update.
    When time, triggers clustering function for outlier detection.

    """

    def __init__(self, username='', password='', project_id='', api_url_base=''):
        """
        Director class constructor.

        Parameters
        ----------
        username : str
            DT Studio service account key.
        password : str
            DT Studio service account secret.
        project_id : str
            DT Studio project identifier.
        api_url_base : str
            Endpoint for API.

        """

        # give to self
        self.username     = username
        self.password     = password
        self.project_id   = project_id
        self.api_url_base = api_url_base

        # variables
        self.last_update = -1

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
        parser = argparse.ArgumentParser(description='Outlier detection for multistream temperature data.')

        # get UTC time now
        now = (datetime.datetime.utcnow().replace(microsecond=0)).isoformat() + 'Z'

        # general arguments
        parser.add_argument('--starttime', metavar='', help='Event history UTC starttime [YYYY-MM-DDTHH:MM:SSZ].', required=False, default=now)
        parser.add_argument('--endtime',   metavar='', help='Event history UTC endtime [YYYY-MM-DDTHH:MM:SSZ].',   required=False, default=now)
        parser.add_argument('--timestep',  metavar='', help='Time in seconds between clusterings.', required=False, type=int, default=prm.timestep)
        parser.add_argument('--window', metavar='', help='Seconds of data in clustering data window.', required=False, type=int, default=prm.window)

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
        """
        Fetch list of all devices in project from API.

        """

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
        self.sensor_ids   = {}
        idx               = 0

        # iterate list of devices
        for device in self.project_devices:
            # get device id
            device_id = os.path.basename(device['name'])

            # accept only labeled devices
            if prm.project_sensor_label in device['labels'].keys():
                # accept only temperature sensors
                if device['type'] == 'temperature':
                    # append an initialised desk object
                    self.temperatures.append(Temperature(device, device_id))
                    self.sensor_ids[device_id] = idx
                    idx += 1


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

        # check if known id
        if source_id in self.sensor_ids:
            # find sensor to related id
            sensor = self.temperatures[self.sensor_ids[source_id]]
            if sensor.sensor_id == source_id:
                # cout
                if cout: print('-- New Event for {}.'.format(source_id))
            
                # serve event to desk
                sensor.new_event_data(event_data)

                return True
        return False


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

        Parameters
        ----------
        plot : bool
            Will generate visualization after running history if True.

        """

        # do nothing if starttime not given
        if not self.fetch_history:
            return

        # get list of hsitoric events
        self.__fetch_event_history()
        
        # generate unixtime axis for all events in history
        n_events               = len(self.event_history)
        event_history_unixtime = [hlp.convert_event_data_timestamp(h['data']['temperature']['updateTime'])[1] for h in self.event_history]

        # time parameters
        unix_start = event_history_unixtime[0]
        unix_step  = 1
        unix_now   = unix_start
        unix_end   = event_history_unixtime[-1]

        # simulate time
        i  = 0
        ic = 0
        while unix_now <= unix_end:
            # print progress
            ic = hlp.loop_progress(ic, i, n_events, 15)

            # catch up with events that have "occured"
            while i < n_events and event_history_unixtime[i] < unix_now:
                # serve event to self
                self.__new_event_data(self.event_history[i], cout=False)

                # iterate
                i += 1

            # plot if timestep has passed
            if self.__check_timestep(unix_now):
                # execute clustering outlier detection
                self.__cluster(unix_now)

            # iterate time
            unix_now += unix_step

        # plot
        if not self.args['no_plot']:
            print('\nThis plot is blocking.')
            print('Closing it will start a stream with a non-blocking plot.')
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
        
                # get response from API
                response = requests.get(self.stream_endpoint, auth=(self.username, self.password), headers={'accept':'text/event-stream'}, stream=True, params=self.stream_params)
                client = sseclient.SSEClient(response)
        
                # listen for events
                print('Connected.')
                for event in client.events():
                    # new data received
                    event_data = json.loads(event.data)['result']['event']
        
                    # serve event to director
                    served = self.__new_event_data(event_data)

                    # execute clustering outlier detection
                    if served:
                        self.__cluster(time.time())
        
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


    def __check_timestep(self, unixtime):
        """
        Check if more time than --timestep has passed since last heatmap update.

        Parameters
        ----------
        unixtime : int
            Seconds since 01-Jan 1970.

        Returns
        -------
        return : bool
            True if time to update heatmap.
            False if we're still waiting.

        """

        # check time since last update
        if self.last_update < 0:
            # update time to this event time
            self.last_update = unixtime
            return False

        elif unixtime - self.last_update > self.args['timestep']:
            # update timer to this event time
            self.last_update = unixtime
            return True


    def __cluster(self, ux_now):
        """
        Window, preprocess and cluster data with the aim of detecting outliers.

        Parameters
        ----------
        ux_now : int
            Unixtime at the moment of call.

        """

        # exit if data is missing
        for t in self.temperatures:
            if len(t.unixtime) < 1:
                return

        # exit if less time than a window width has passed
        first_event_ux = max([t.unixtime[0] for t in self.temperatures])
        if ux_now - first_event_ux < self.args['window']:
            return

        # define interval left- and right flank
        tl = int(ux_now - self.args['window'])
        tr = int(ux_now)

        # get data from defined window interval
        rex, rey, flag = self.__isolate_recent_window(tl, tr)

        # don't perform DBSCAN clustering if we're missing data
        if not flag:
            return

        # sklearn dbscan implementation
        c = DBSCAN(eps=self.__dynamic_epsilon(rey)*prm.threshold_modifier, min_samples=prm.minimum_cluster_size).fit(rey)

        # update outlier triggers for each sensor
        self.__update_outlier_triggers(c.labels_, tl)


    def __isolate_recent_window(self, tl, tr):
        """
        Isolate the most recent window of data for use in clustering.
        Data is uniformly resampled to synchronize events.

        Parameters
        tl : int
            Window unixtime left flank.
        tr : int
            Window unixtime right flank.

        Returns
        -------
        rex : array_like
            Resampled window x-axis.
        rey : array_like
            Resampled window y-axis.

        """

        # cut series to window interval
        xx = []
        yy = []
        for t in self.temperatures:
            x = np.array(t.unixtime)
            y = np.array(t.values)[(x >= tl) & (x <= tr)]
            x = x[(x >= tl) & (x <= tr)]

            # skip if missing data
            if len(y) < 2:
                return None, None, False

            # append to window list
            xx.append(x)
            yy.append(y)

        # set interval limits to inner timestamps for series
        for x in xx:
            if x[0] > tl:
                tl = x[0]
            if x[-1] < tr:
                tr = x[-1]

        # create a common x-axis for interpolation for 15 minute period (900s)
        rex = np.arange(tl, tr, 900)
        rey = []

        # interpolate series to rex axis
        for i in range(len(xx)):
            # interpolate
            f = interp1d(xx[i], yy[i], kind='linear')
            rey.append(f(rex))

        # convert from list to numpy array
        rey = np.array(rey)

        return rex, rey, True



    def __update_outlier_triggers(self, labels, tl):
        """
        Set sensor outlier triggers to 1 if label is not in main group.

        Parameters
        ----------
        labels : list
            List of cluster labels found by DBSCAN.
        tl : int
            Window unixtime left flank.

        """

        # find most occuring label index
        imax = np.argmax(np.bincount(labels[labels >= 0]))

        # set outlier triggers for sensors
        for i, t in enumerate(self.temperatures):
            # outlier if sensor label is not in main group
            if labels[i] != imax or labels[i] < 0:
                # set outlier triggers in window to 1
                ix = len(t.values)-1
                while ix >= 0 and t.unixtime[ix] > tl:
                    t.outlier[ix] = 1
                    ix -= 1


    def __dynamic_epsilon(self, x):
        """
        Calculate DBSCAN epsilon based on data.

        Parameters
        ----------
        x : array_like
            Feature array of data for which epsilon is calculated.

        Returns
        -------
        epsilon : float
            DBSCAN epsilon value for data.

        """

        m = np.median(x, axis=0)
        mm = []
        for y in x:
            d = 0
            for i in range(len(y)):
                d += (y[i]-m[i])**2
            d = np.sqrt(d)
            mm.append(d)

        return np.median(mm)


    def initialise_plot(self):
        self.fig, self.ax = plt.subplots()


    def plot(self, blocking=True, show=True):
        # initialise if not open
        if not hasattr(self, 'ax') or not plt.fignum_exists(self.fig.number):
            self.initialise_plot()

        # refresh plot
        self.ax.cla()

        # draw sensor data
        sensor = self.temperatures[0]
        for i, sensor in enumerate(self.temperatures):
            outlier = np.array(sensor.outlier)
            good = np.zeros(len(sensor.values))
            good[:] = sensor.values
            good[outlier==1] = None
            bad  = np.zeros(len(sensor.values))
            bad[:] = sensor.values
            bad[outlier==0] = None

            if i == 0:
                self.ax.plot(sensor.get_timestamps(), good, color=stl.colors['vb1'], linewidth=1, linestyle=':', label='temperature')
                self.ax.plot(sensor.get_timestamps(), bad,  color=stl.colors['ss2'], linewidth=2, linestyle='-', label='outlier')
            else:
                self.ax.plot(sensor.get_timestamps(), good, color=stl.colors['vb1'], linewidth=1, linestyle=':')
                self.ax.plot(sensor.get_timestamps(), bad,  color=stl.colors['ss2'], linewidth=2, linestyle='-')

        # set axis labels
        self.ax.set_xlabel('timestamp')
        self.ax.set_ylabel('temperature [degC]')
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['top'].set_visible(False)
        self.ax.yaxis.set_ticks_position('left')
        self.ax.xaxis.set_ticks_position('bottom')
        self.ax.legend()

        if blocking:
            if show:
                plt.show()
            else:
                plt.waitforbuttonpress()
        else:
            plt.pause(0.01)

