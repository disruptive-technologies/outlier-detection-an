# label name to look for in project
project_sensor_label = 'outlier_detection'

timestep = 60*60*1   # seconds between each clustering call [s]
window   = 60*60*3*1 # width of data window used in clustering [s]

threshold_modifier   = 2 # multiplier for clustering epsilon
minimum_cluster_size = 2 # minimum number of data series which can form a clustering

