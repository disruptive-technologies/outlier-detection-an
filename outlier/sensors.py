# project
import outlier.helpers as hlp


class Sensor():
    """
    One Sensor class instance per sensor in project used for outlier detection.
    Receives new event data from director.

    """

    def __init__(self, device, sensor_id):
        """
        Constructor for Sensor class.

        Parameters
        ----------
        device : dict
            Dictionary of device information fetched from API.
        sensor_id : str
            Sensor identifier.

        """

        # give to self
        self.device    = device
        self.sensor_id = sensor_id

        # initialise lists
        self.unixtime = []
        self.values   = []
        self.anomaly  = []


    def get_timestamps(self):
        return hlp.ux2tx(self.unixtime)
    

    def get_values(self):
        return self.values


class Temperature(Sensor):
    """
    Child of Sensor class representing temperature sensors specificly.

    """

    def new_event_data(self, event):
        """
        Receive new temperature event data from director and append to lists.

        Parameters
        ----------
        event : dict
            Dictionary of event data information.

        """

        # convert to unixtime
        _, ux = hlp.convert_event_data_timestamp(event['data']['temperature']['updateTime'])

        # append
        self.unixtime.append(ux)
        self.values.append(event['data']['temperature']['value'])
        self.anomaly.append(0)

