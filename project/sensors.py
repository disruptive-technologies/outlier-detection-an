# project
import project.helpers as hlp


class Sensor():

    def __init__(self, device, sensor_id, args):
        # give to self
        self.device    = device
        self.sensor_id = sensor_id
        self.args      = args

        # initialise lists
        self.unixtime = []
        self.values   = []


    def get_timestamps(self):
        return hlp.ux2tx(self.unixtime)
    

    def get_values(self):
        return self.values


class Temperature(Sensor):

    def new_event_data(self, event):
        # convert to unixtime
        _, ux = hlp.convert_event_data_timestamp(event['data']['temperature']['updateTime'])

        # append
        self.unixtime.append(ux)
        self.values.append(event['data']['temperature']['value'])


class Proximity(Sensor):

    def new_event_data(self, event):
        # convert to unixtime
        _, ux = hlp.convert_event_data_timestamp(event['data']['objectPresent']['updateTime'])

        # convert state to boolean
        if event['data']['objectPresent']['state'] == 'PRESENT':
            state = True
        else:
            state = False

        # append
        self.unixtime.append(ux)
        self.values.append(state)

        # update own state
        self.state = state

