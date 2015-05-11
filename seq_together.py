#! /usr/bin/python
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
#
#  To install on this machine: matplotlib, numpy

from __future__ import print_function

##################################################
##                   IMPORTS                    ##
##################################################

import argparse
import common as co
import glob
import matplotlib
# Do not use any X11 backend
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mptcp
import numpy as np
import os
import os.path
import pickle
import sys
import tcp

##################################################
##                  ARGUMENTS                   ##
##################################################

parser = argparse.ArgumentParser(
    description="Summarize sequence number together in one graph")
parser.add_argument("-s",
                    "--stat", help="directory where the stat files are stored", default=co.DEF_STAT_DIR+'_'+co.DEF_IFACE)
parser.add_argument('-S',
                    "--sums", help="directory where the summary graphs will be stored", default=co.DEF_SUMS_DIR+'_'+co.DEF_IFACE)
parser.add_argument("-d",
                    "--dirs", help="list of directories to aggregate", nargs="+")
parser.add_argument("-c",
                    "--csv", help="directory where csvs/xpls are located")

args = parser.parse_args()

stat_dir_exp = os.path.abspath(os.path.expanduser(args.stat))
sums_dir_exp = os.path.abspath(os.path.expanduser(args.sums))
csv_dir_exp = os.path.abspath(os.path.expanduser(args.csv))

co.check_directory_exists(sums_dir_exp)

def check_in_list(dirpath, dirs):
    """ Check if dirpath is one of the dir in dirs, True if dirs is empty """
    if not dirs:
        return True
    return os.path.basename(dirpath) in dirs


def fetch_data(dir_exp):
    co.check_directory_exists(dir_exp)
    dico = {}
    for dirpath, dirnames, filenames in os.walk(dir_exp):
        if check_in_list(dirpath, args.dirs):
            for fname in filenames:
                try:
                    stat_file = open(os.path.join(dirpath, fname), 'r')
                    dico[fname] = pickle.load(stat_file)
                    stat_file.close()
                except IOError as e:
                    print(str(e) + ': skip stat file ' + fname, file=sys.stderr)
    return dico

connections = fetch_data(stat_dir_exp)


def seq_d2s_all_connections():
    for fname, conns in connections.iteritems():
        seqs = {co.WIFI: [], co.CELL: []}
        start_connections = []

        if fname.startswith('mptcp'):
            for csv_path in glob.glob(os.path.join(csv_dir_exp, fname + '_*.csv')):
                csv_fname = os.path.basename(csv_path)
                # Preprocessing, avoid wasting time with not interesting files
                from_server_to_smartphone = mptcp.is_reverse_connection(csv_fname)
                if not from_server_to_smartphone:
                    continue
                conn_id = mptcp.get_connection_id(csv_fname)

                # Opening of the file
                try:
                    csv_file = open(csv_path)
                    data = csv_file.readlines()
                    csv_file.close()
                except IOError as e:
                    print(str(e))
                    continue

                # Now process the file
                conn = connections[fname][conn_id]
                start_connections.append(conn.attr[co.START])
                flow_interface = {}
                for flow_id, flow in conn.flows.iteritems():
                    flow_interface[flow_id] = flow.attr[co.IF]

                for line in data:
                    split_line = line.split(',')

                    if int(split_line[3]) == 1:
                        # MAP
                        timestamp = float(split_line[0])
                        seq_start = int(split_line[1])
                        flow_id = int(split_line[2]) - 1
                        # is_ack = False # int(split_line[3]) == 1
                        seq_end = int(split_line[4])
                        reinject_flow = int(split_line[5]) - 1 # If not negative, the flow where packet was first seen
                        seqs[flow_interface[flow_id]].append((timestamp, seq_end, reinject_flow, conn_id))

            # Now put all together on a same graph
            offsets = {}
            tot_offset = {co.WIFI: 0, co.CELL: 0}
            seqs_plot = {co.WIFI: [], co.CELL: []}
            for ith, seqs_ith in seqs.iteritems():
                seqs_sort = sorted(seqs_ith, key=lambda elem: elem[0])
                for elem in seqs_sort:
                    if elem[3] not in offsets:
                        offsets[elem[3]] = elem[1]
                        seqs_plot[ith].append((elem[0], tot_offset[ith]))
                    else:
                        seqs_plot[ith].append((elem[0], tot_offset[ith] + (elem[1] - offsets[elem[3]])))
                        tot_offset[ith] += elem[1] - offsets[elem[3]]
                        offsets[elem[3]] = elem[1]

            start_ts = min(seqs_plot[co.WIFI][0][0], seqs_plot[co.CELL][0][0])
            fig, ax = plt.subplots()
            ax.plot([x[0] for x in seqs_plot[co.WIFI]], [x[1] for x in seqs_plot[co.WIFI]], 'r-')
            ax.plot([x[0] for x in seqs_plot[co.CELL]], [x[1] for x in seqs_plot[co.CELL]], 'b-')
            plt.savefig(os.path.join(sums_dir_exp, fname + '.pdf'))

        elif fname.startswith('tcp'):
            for xpl_path in glob.glob(os.path.join(csv_dir_exp, fname + '_*.xpl')):
                xpl_fname = os.path.basename(xpl_path)
                # Preprocessing, avoid wasting time with not interesting files
                conn_id, from_server_to_smartphone = tcp.get_flow_name(xpl_fname)
                if not from_server_to_smartphone:
                    continue

                # Opening of the file
                try:
                    xpl_file = open(xpl_path)
                    data = xpl_file.readlines()
                    xpl_file.close()
                except IOError as e:
                    print(str(e))
                    continue

                # Now process the file
                conn = connections[fname][conn_id]
                start_connections.append(conn.flow.attr[co.START])
                interface = conn.flow.attr[co.IF]
                for line in data:
                    if line.startswith("uarrow") or line.startswith("diamond"):
                        split_line = line.split(" ")
                        if ((not split_line[0] == "diamond") or (len(split_line) == 4 and "white" in split_line[3])):
                            time = float(split_line[1])
                            seqs[interface].append([time, int(split_line[2]), conn_id])

            # Now put all togetger on a same graph
            offsets = {}
            tot_offset = {co.WIFI: 0, co.CELL: 0}
            seqs_plot = {co.WIFI: [], co.CELL: []}
            for ith, seqs_ith in seqs.iteritems():
                seqs_sort = sorted(seqs_ith, key=lambda elem: elem[0])
                for elem in seqs_sort:
                    if elem[2] not in offsets:
                        offsets[elem[2]] = elem[1]
                        seqs_plot[ith].append((elem[0], tot_offset[ith]))
                    else:
                        seqs_plot[ith].append((elem[0], tot_offset[ith] + (elem[1] - offsets[elem[2]])))
                        tot_offset[ith] += elem[1] - offsets[elem[2]]
                        offsets[elem[2]] = elem[1]

            start_ts = min(seqs_plot[co.WIFI][0][0], seqs_plot[co.CELL][0][0])
            fig, ax = plt.subplots()
            ax.plot([x[0] for x in seqs_plot[co.WIFI]], [x[1] for x in seqs_plot[co.WIFI]], 'r-')
            ax.plot([x[0] for x in seqs_plot[co.CELL]], [x[1] for x in seqs_plot[co.CELL]], 'b-')
            plt.savefig(os.path.join(sums_dir_exp, fname + '.pdf'))

seq_d2s_all_connections()


def collect_seq():
    seqs = {}
    for csv_path in glob.glob(os.path.join(csv_dir_exp, '*.csv')):
        csv_fname = os.path.basename(csv_path)
        try:
            csv_file = open(csv_path)
            data = csv_file.readlines()
            csv_file.close()
        except IOError as e:
            print(str(e))
            continue

        seqs_csv = []

        for line in data:
            split_line = line.split(',')
            if len(split_line) == 6:
                if int(split_line[3]) == 0:
                    # ACK
                    timestamp = float(split_line[0])
                    seq_ack = int(split_line[1])
                    flow_id = int(split_line[2]) - 1
                    # is_ack = True # int(split_line[3]) == 0
                    # dummy = int(split_line[4])
                    # dummy_2 = int(split_line[5])
                    seqs_csv.append((timestamp, seq_ack, flow_id))

                elif int(split_line[3]) == 1:
                    # MAP
                    timestamp = float(split_line[0])
                    seq_start = int(split_line[1])
                    flow_id = int(split_line[2]) - 1
                    # is_ack = False # int(split_line[3]) == 1
                    seq_end = int(split_line[4])
                    reinject_flow = int(split_line[5]) - 1 # If not negative, the flow where packet was first seen
                    seqs_csv.append((timestamp, seq_start, flow_id, seq_end, reinject_flow))

        seqs[csv_fname] = seqs_csv

    return seqs
