
import argparse
import copy
import datetime
import glob
import math
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import traceback


# Avoid Type 3 fonts (conferences don't tend to like them).
matplotlib.rcParams['pdf.fonttype'] = 42
matplotlib.rcParams['ps.fonttype'] = 42

if platform.system() != "Windows":
    import fcntl

# If a server's id appears as a key in this dictionary, it means we
# have started cp_node running on that node. The value of each entry is
# a Popen object that can be used to communicate with the node.
active_nodes = {}

# If a server's id appears as a key in this dictionary, it means we
# have started homa_prio running on that node. The value of each entry is
# a Popen object for the homa_prio instance; if this is terminated, then
# the homa_prio process will end
homa_prios = {}

# The range of nodes currently running cp_node servers.
server_nodes = range(0,0)

# Directory containing log files.
log_dir = ''

# Open file (in the log directory) where log messages should be written.
log_file = 0

# Indicates whether we should generate additional log messages for debugging
verbose = False

# Defaults for command-line options; assumes that servers and clients
# share nodes.
default_defaults = {
    'gbps':                0.0,
    # Note: very large numbers for client_max hurt Homa throughput with
    # unlimited load (throttle queue inserts take a long time).
    'client_max':          200,
    'client_ports':        3,
    'log_dir':             'logs/' + time.strftime('%Y%m%d%H%M%S'),
    'mtu':                 0,
    'no_trunc':            '',
    'protocol':            'homa',
    'port_receivers':      3,
    'port_threads':        3,
    'seconds':             5,
    'server_ports':        3,
    'tcp_client_ports':    4,
    'tcp_port_receivers':  1,
    'tcp_server_ports':    8,
    'tcp_port_threads':    1,
    'unloaded':            0,
    'unsched':             0,
    'unsched_boost':       0.0,
    'workload':            ''
}

# Keys are experiment names, and each value is the digested data for that
# experiment.  The digest is itself a dictionary containing some or all of
# the following keys:
# rtts:            A dictionary with message lengths as keys; each value is
#                  a list of the RTTs (in usec) for all messages of that length.
# total_messages:  Total number of samples in rtts.
# lengths:         Sorted list of message lengths, corresponding to buckets
#                  chosen for plotting
# cum_frac:        Cumulative fraction of all messages corresponding to each length
# counts:          Number of RTTs represented by each bucket
# p50:             List of 50th percentile rtts corresponding to each length
# p99:             List of 99th percentile rtts corresponding to each length
# p999:            List of 999th percentile rtts corresponding to each length
# slow_50:         List of 50th percentile slowdowns corresponding to each length
# slow_99:         List of 99th percentile slowdowns corresponding to each length
# slow_999:        List of 999th percentile slowdowns corresponding to each length
digests = {}

# A dictionary where keys are message lengths, and each value is the median
# unloaded RTT (usecs) for messages of that length.
unloaded_p50 = {}

# Keys are filenames, and each value is a dictionary containing data read
# from that file. Within that dictionary, each key is the name of a column
# within the file, and the value is a list of numbers read from the given
# column of the given file.
data_from_files = {}

# Time when this benchmark was run.
date_time = str(datetime.datetime.now())

# Standard colors for plotting
tcp_color =      '#00B000'
tcp_color2 =     '#5BD15B'
tcp_color3 =     '#96E296'
homa_color =     '#1759BB'
homa_color2 =    '#6099EE'
homa_color3 =    '#A6C6F6'
dctcp_color =    '#7A4412'
dctcp_color2 =   '#CB701D'
dctcp_color3 =   '#EAA668'
unloaded_color = '#d62728'

# Default bandwidths to use when running all of the workloads.
load_info = [["w1", 1.4], ["w2", 3.2], ["w3", 14], ["w4", 20], ["w5", 20]]

# PyPlot color circle colors:
pyplot_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']

def boolean(s):
    """
    Used as a "type" in argparse specs; accepts Boolean-looking things.
    """
    map = {'true': True, 'yes': True, 'ok': True, "1": True, 'y': True,
        't': True, 'false': False, 'no': False, '0': False, 'f': False,
        'n': False}
    lc = s.lower()
    if lc not in map:
        raise ValueError("Expected boolean value, got %s" % (s))
    return map[lc]

def log(message):
    """
    Write the a log message both to stdout and to the cperf log file.

    message:  The log message to write; a newline will be appended.
    """
    global log_file
    print(message)
    log_file.write(message)
    log_file.write("\n")

def vlog(message):
    """
    Log a message, like log, but if verbose logging isn't enabled, then
    log only to the cperf log file, not to stdout.

    message:  The log message to write; a newline will be appended.
    """
    global log_file, verbose
    if verbose:
        print(message)
    log_file.write(message)
    log_file.write("\n")

def read_rtts(file, rtts):
    """
    Read a file generated by cp_node's "dump_times" command and add its
    data to the information present in rtts.

    file:    Name of the log file.
    rtts:    Dictionary whose keys are message lengths; each value is a
             list of all of the rtts recorded for that message length (in usecs)
    Returns: The total number of rtts read from the file.
    """

    total = 0
    f = open(file, "r")
    for line in f:
        stripped = line.strip()
        if stripped[0] == '#':
            continue
        words = stripped.split()
        if (len(words) < 2):
            print("Line in %s too short (need at least 2 columns): '%s'" %
                    (file, line))
            continue
        length = int(words[0])
        usec = float(words[1])
        if length in rtts:
            rtts[length].append(usec)
        else:
            rtts[length] = [usec]
        total += 1
    f.close()
    return total

def get_buckets(rtts, total):
    """
    Generates buckets for histogramming the information in rtts.

    rtts:     A collection of message rtts, as returned by read_rtts
    total:    Total number of samples in rtts
    Returns:  A list of <length, cum_frac> pairs, in sorted order. The length
              is the largest message size for a bucket, and cum_frac is the
              fraction of all messages with that length or smaller.
    """
    buckets = []
    cumulative = 0
    for length in sorted(rtts.keys()):
        cumulative += len(rtts[length])
        buckets.append([length, cumulative/total])
    return buckets

def get_digest(file):
    """
    Returns an element of digest that contains data for a particular
    experiment; if this is the first request for a given experiment, the
    method reads the data for experiment and generates the digest. For
    each new digest generated, a .data file is generated in the "reports"
    subdirectory of the log directory.

    experiment:  Name of the desired experiment
    """
    log_dir

    digest = {}
    digest["rtts"] = {}
    digest["total_messages"] = 0
    digest["lengths"] = []
    digest["cum_frac"] = []
    digest["counts"] = []
    digest["p50"] = []
    digest["p99"] = []
    digest["p999"] = []
    digest["slow_50"] = []
    digest["slow_99"] = []
    digest["slow_999"] = []

    # Read in the RTT files for this experiment.
    sys.stdout.write("Reading RTT data for %s experiment: " % (file))
    sys.stdout.flush()
    digest["total_messages"] = read_rtts(file, digest["rtts"])
    sys.stdout.write("#")
    sys.stdout.flush()
    print("")

    if len(unloaded_p50) == 0:
        raise Exception("No unloaded data: must invoked set_unloaded")

    rtts = digest["rtts"]
    buckets = get_buckets(rtts, digest["total_messages"])
    bucket_length, bucket_cum_frac = buckets[0]
    next_bucket = 1
    bucket_rtts = []
    bucket_slowdowns = []
    bucket_count = 0
    cur_unloaded = unloaded_p50[min(unloaded_p50.keys())]
    lengths = sorted(rtts.keys())
    lengths.append(999999999)            # Force one extra loop iteration
    for length in lengths:
        if length > bucket_length:
            digest["lengths"].append(bucket_length)
            digest["cum_frac"].append(bucket_cum_frac)
            digest["counts"].append(bucket_count)
            if len(bucket_rtts) == 0:
                bucket_rtts.append(0)
                bucket_slowdowns.append(0)
            bucket_rtts = sorted(bucket_rtts)
            digest["p50"].append(bucket_rtts[bucket_count//2])
            digest["p99"].append(bucket_rtts[bucket_count*99//100])
            digest["p999"].append(bucket_rtts[bucket_count*999//1000])
            bucket_slowdowns = sorted(bucket_slowdowns)
            digest["slow_50"].append(bucket_slowdowns[bucket_count//2])
            digest["slow_99"].append(bucket_slowdowns[bucket_count*99//100])
            digest["slow_999"].append(bucket_slowdowns[bucket_count*999//1000])
            if next_bucket >= len(buckets):
                break
            bucket_rtts = []
            bucket_slowdowns = []
            bucket_count = 0
            bucket_length, bucket_cum_frac = buckets[next_bucket]
            next_bucket += 1
        if length in unloaded_p50:
            cur_unloaded = unloaded_p50[length]
        bucket_count += len(rtts[length])
        for rtt in rtts[length]:
            bucket_rtts.append(rtt)
            bucket_slowdowns.append(rtt/cur_unloaded)
    log("Digest finished for %s" % (file))

    dir = "%s/reports" % (log_dir)
    f = open("%s/reports/%s.data" % (log_dir, file), "w")
    f.write("# Digested data for %s experiment, run at %s\n"
            % (file, date_time))
    f.write("# length  cum_frac  samples     p50      p99     p999   "
            "s50    s99    s999\n")
    for i in range(len(digest["lengths"])):
        f.write(" %7d %9.6f %8d %7.1f %8.1f %8.1f %5.1f %6.1f %7.1f\n"
                % (digest["lengths"][i], digest["cum_frac"][i],
                digest["counts"][i], digest["p50"][i], digest["p99"][i],
                digest["p999"][i], digest["slow_50"][i],
                digest["slow_99"][i], digest["slow_999"][i]))
    f.close()

    return digest