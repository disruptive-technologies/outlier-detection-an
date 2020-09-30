# packages
import sys
import numpy  as np
import pandas as pd


def print_error(text, terminate=True):
    """
    Print an error message and terminate as desired.

    Parameters
    ----------
    terminate : bool
        Terminate execution if True.
    """

    print('ERROR: {}'.format(text))
    if terminate:
        sys.exit()


def convert_event_data_timestamp(ts):
    """
    Convert the default event_data timestamp format to Pandas and unixtime format.

    Parameters
    ----------
    ts : str
        UTC timestamp in custom API event data format.

    Returns
    -------
    timestamp : datetime
        Pandas Timestamp object format.
    unixtime : int
        Integer number of seconds since 1 January 1970.

    """

    timestamp = pd.to_datetime(ts)
    unixtime  = pd.to_datetime(np.array([ts])).astype(int)[0] // 10**9

    return timestamp, unixtime


def json_sort_key(json):
    """
    Return the event update time converted to unixtime.

    Parameters
    ----------
    json : dictionary
        Event data json imported as dictionary.

    Returns
    -------
    unixtime : int
        Event data update time converted to unixtime.

    """

    keys = json['data'].keys()
    if 'temperature' in keys:
        typename = 'temperature'
    elif 'objectPresent' in keys:
        typename = 'objectPresent'
    else:
        print(json)
        print_error('KeyError in json_sort.', terminate=True)
    timestamp = json['data'][typename]['updateTime']
    _, unixtime = convert_event_data_timestamp(timestamp)
    return unixtime


def loop_progress(i_track, i, n_max, n_steps, name=None, acronym=' '):
    """
    Print loop progress to console.

    Parameters
    ----------
    i_track : int
        Tracks how far the progress has come:
    i : int
        Current index in loop.
    n_max : int
        Maximum value which indicates progress done.
    n_steps : int
        Number of steps to be counted.

    """

    # number of indices in each progress element
    part = n_max / n_steps

    if i_track == 0:
        # print empty bar
        print('    |')
        if name is None:
            print('    └── Progress:')
        else:
            print('    └── {}:'.format(name))
        print('        ├── [ ' + (n_steps-1)*'-' + ' ] ' + acronym)
        i_track = 1
    elif i > i_track + part:
        # update tracker
        i_track = i_track + part

        # print bar
        print('        ├── [ ' + int(i_track/part)*'#' + (n_steps - int(i_track/part) - 1)*'-' + ' ] ' + acronym)

    # return tracker
    return i_track


def ux2tx(ux):
    """
    Convert unixtime to datetime format.
    Parameters
    ----------
    ux : int 
        Seconds since 01-01-1970.
    returns:
    dt : datetime 
        Pandas datetime format.
    """

    # create datetime
    dt = pd.to_datetime(ux, unit='s')

    return dt
