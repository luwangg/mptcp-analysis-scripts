# -*- coding: utf-8 -*-
#
#  Copyright 2015 Matthieu Baerts & Quentin De Coninck
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.

from __future__ import print_function

##################################################
##                   IMPORTS                    ##
##################################################

import os
import Gnuplot
import pickle

Gnuplot.GnuplotOpts.default_term = 'pdf'


##################################################
##               COMMON CONSTANTS               ##
##################################################

# Following constants are used to make the code cleaner and more robust (for dictionary)
# Those are mainly determined by the output of mptcptrace
RMNET = 'rmnet'
WIFI = 'wifi'
# IPv4 or IPv6
TYPE = 'type'
# Interface: RMNET or WIFI
IF = 'interface'
# Source IP address
SADDR = 'saddr'
# Destination IP address
DADDR = 'daddr'
# Source port
SPORT = 'sport'
# Destination port
DPORT = 'dport'
# Window scale for source
WSCALESRC = 'wscalesrc'
# Window scale for destination
WSCALEDST = 'wscaledst'
# Duration of a connection
DURATION = 'duration'
# Number of packets from source to destination
PACKS_S2D = 'packets_source2destination'
# Number of packets from destination to source
PACKS_D2S = 'packets_destination2source'
# Number of bytes from source to destination
BYTES_S2D = 'bytes_source2destination'
# Number of bytes from destination to source
BYTES_D2S = 'bytes_destination2source'

##################################################
##               COMMON FUNCTIONS               ##
##################################################


def save_object(obj, fname):
    """ Save the object obj in the file with filename fname """
    file = open(fname, 'wb')
    file.write(pickle.dumps(obj))
    file.close()


def load_object(fname):
    """ Return the object contained in the file with filename fname """
    file = open(fname, 'rb')
    obj = pickle.loads(file.read())
    file.close()
    return obj


def check_directory_exists(directory):
    """ Check if the directory exists, and create it if needed
        If directory is a file, exit the program
    """
    if os.path.exists(directory):
        if not os.path.isdir(directory):
            print(directory + " is a file: stop")
    else:
        os.makedirs(directory)


def is_number(s):
    """ Check if the str s is a number """
    try:
        float(s)
        return True
    except ValueError:
        return False

def count_mptcp_subflows(data):
    """ Count the number of subflows of a MPTCP connection """
    count = 0
    for key, value in data.iteritems():
        # There could have "pure" data in the connection
        if isinstance(value, dict):
            count += 1

    return count
