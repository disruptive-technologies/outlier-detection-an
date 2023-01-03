import argparse
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import disruptive as dt
from sklearn.cluster import DBSCAN
import matplotlib.pyplot as plt


FS = 60 * 15  # resample rate [seconds]


def parse_sysargs() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--project-id',
        type=str,
        default='',
        help='target project ID',
    )
    parser.add_argument(
        '-f', '--file',
        type=str,
        default='',
        help='use data in file',
    )
    parser.add_argument(
        '--devices',
        type=str,
        default='',
        help='comma-separated list of device IDs',
    )
    parser.add_argument(
        '--days',
        type=int,
        default=3,
        help='number of days for which data is pulled',
    )
    parser.add_argument(
        '--timestep',
        type=int,
        default=60*60*1,
        help='seconds between each cluster call',
    )
    parser.add_argument(
        '--window',
        type=int,
        default=60*60*3,
        help='seconds of data in each window',
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='print debug data',
    )
    args = parser.parse_args()

    # Require either a file or project ID.
    if len(args.project_id) < 1 and len(args.file) < 1:
        raise ValueError('provide either --project-id or --file')

    # Format comma-separated string of device IDs to list[str].
    if len(args.devices) > 0:
        args.devices = args.devices.split(',')

    return args


def fetch_event_history(project_id: str,
                        device_ids: list[str],
                        days: int,
                        file_path: str,
                        ) -> tuple[list[pd.DatetimeIndex], np.ndarray]:
    if len(file_path) > 0:
        events_df = pd.read_csv(file_path)
    else:
        if len(device_ids) < 1:
            # Pull all temperature devices available in project.
            devices = dt.Device.list_devices(
                project_id=project_id,
                device_types=[dt.Device.TEMPERATURE],
            )
            device_ids = [d.device_id for d in devices]

        # For each device, pull <days> of data.
        events: dt.EventHistory = dt.EventHistory()
        for device_id in device_ids:
            events += dt.EventHistory.list_events(
                device_id=device_id,
                project_id=project_id,
                event_types=[dt.events.TEMPERATURE],
                start_time=datetime.now() - timedelta(days=days),
            )

        # Convert to pandas DataFrame.
        events_df = events.to_dataframe()[[
            'sample_time',
            'value',
            'device_id',
        ]]

    # Resample data to predetermined resolution.
    events_df.set_index('sample_time', inplace=True, drop=True)
    events_df.index = pd.to_datetime(events_df.index)

    resampled_df = events_df.groupby('device_id')[['value']] \
        .resample(f'{FS}s').fillna('nearest').interpolate()

    return (
        [v[1] for v in resampled_df.unstack().transpose().index.values],
        resampled_df.unstack().fillna(method='ffill')
        .fillna(method='bfill').values
    )


def update_labels(labels_matrix: np.ndarray,
                  new_labels: np.ndarray,
                  i: int,
                  j: int,
                  ) -> np.ndarray:
    """
    Update `events_labels` matrix with new
    cluster classification from index i to j.

    """

    if len(np.unique(new_labels)) > 1:
        # Determine most common label in cluster classification.
        imax = np.argmax(np.bincount(new_labels[new_labels >= 0]))
        labels_matrix[new_labels != imax, i:j] = 1

    return labels_matrix


def dynamic_epsilon(x) -> float:
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

    return float(np.median(mm)) * 2


if __name__ == '__main__':
    args = parse_sysargs()

    if args.verbose:
        dt.log_level = dt.logging.DEBUG

    # Fetch historic data.
    timeaxis, events = fetch_event_history(
        project_id=args.project_id,
        device_ids=args.devices,
        file_path=args.file,
        days=args.days,
    )

    events_labels = np.zeros(events.shape)

    i = 0
    window_samples = args.window // FS
    timestep_index = args.timestep // FS
    while i + window_samples < events.shape[1]:
        window_data = events[:, i:i+window_samples]

        cluster = DBSCAN(eps=dynamic_epsilon(window_data)).fit(window_data)
        i += timestep_index

        events_labels = update_labels(
            labels_matrix=events_labels,
            new_labels=cluster.labels_,
            i=i,
            j=i+window_samples,
        )

    # Plot result.
    mask = events.copy()
    mask[events_labels == 0] = np.nan

    plt.plot(timeaxis, events.T, ':', color='black')
    plt.plot(timeaxis, mask.T, color='C1')
    plt.xlabel('Timestamp')
    plt.ylabel('Temperature [C]')
    plt.show()
