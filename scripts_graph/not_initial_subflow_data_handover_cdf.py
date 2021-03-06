#! /usr/bin/python
# -*- coding: utf-8 -*-
#
#  Copyright 2015 Quentin De Coninck
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

import argparse
import matplotlib
# Do not use any X11 backend
matplotlib.use('Agg')
matplotlib.rcParams['pdf.fonttype'] = 42
matplotlib.rcParams['ps.fonttype'] = 42
import matplotlib.pyplot as plt
import numpy as np
import os
import sys

# Add root directory in Python path and be at the root
ROOT_DIR = os.path.abspath(os.path.join(".", os.pardir))
os.chdir(ROOT_DIR)
sys.path.append(ROOT_DIR)

import common as co
import common_graph as cog
import mptcp
import tcp

##################################################
##                  ARGUMENTS                   ##
##################################################

parser = argparse.ArgumentParser(
    description="Summarize stat files generated by analyze")
parser.add_argument("-s",
                    "--stat", help="directory where the stat files are stored", default=co.DEF_STAT_DIR + '_' + co.DEF_IFACE)
parser.add_argument('-S',
                    "--sums", help="directory where the summary graphs will be stored", default=co.DEF_SUMS_DIR + '_' + co.DEF_IFACE)
parser.add_argument("-d",
                    "--dirs", help="list of directories to aggregate", nargs="+")

args = parser.parse_args()
stat_dir_exp = os.path.abspath(os.path.join(ROOT_DIR, args.stat))
sums_dir_exp = os.path.abspath(os.path.join(ROOT_DIR, args.sums))
co.check_directory_exists(sums_dir_exp)

##################################################
##                 GET THE DATA                 ##
##################################################

connections = cog.fetch_valid_data(stat_dir_exp, args)
multiflow_connections, singleflow_connections = cog.get_multiflow_connections(connections)

##################################################
##               PLOTTING RESULTS               ##
##################################################

INITIAL_SF = 'Additional SFs'
INITIAL_SFS = '2 Initial SFs'
nb_conns = 0
nb_bytes = {co.C2S: 0, co.S2C: 0}
count_handover = 0
count_0 = {co.C2S: 0, co.S2C: 0}
missing_add_addrs = []
missing_rm_addrs = []
no_add_addrs = []
no_rm_addrs = []

results = {co.C2S: {INITIAL_SF: [], INITIAL_SFS: []}, co.S2C: {INITIAL_SF: [], INITIAL_SFS: []}}
for fname, conns in multiflow_connections.iteritems():
    for conn_id, conn in conns.iteritems():
        # Restrict to connections using at least 2 SFs
        take = False

        nb_flows = 0
        for flow_id, flow in conn.flows.iteritems():
            if flow.attr[co.C2S].get(co.BYTES, 0) > 0 or flow.attr[co.S2C].get(co.BYTES, 0) > 0:
                nb_flows += 1

        if nb_flows >= 2:
            take = True

        if take:
            # Detect now if there is handover
            initial_sf_ts = float('inf')
            min_last_ack = float('inf')
            for flow_id, flow in conn.flows.iteritems():
                if co.START not in flow.attr or flow.attr[co.SADDR] in co.IP_PROXY:
                    continue
                if flow.attr[co.START].total_seconds() < initial_sf_ts:
                    initial_sf_ts = flow.attr[co.START].total_seconds()
                flow_bytes = 0
                for direction in co.DIRECTIONS:
                    flow_bytes += flow.attr[direction].get(co.BYTES_DATA, 0)
                if flow_bytes > 0 and co.TIME_LAST_ACK_TCP in flow.attr[co.S2C] and co.TIME_FIN_ACK_TCP in flow.attr[co.S2C] and flow.attr[co.S2C][co.TIME_LAST_ACK_TCP].total_seconds() > 0.0 and flow.attr[co.S2C][co.TIME_FIN_ACK_TCP].total_seconds() == 0.0:
                    min_last_ack = min(min_last_ack, flow.attr[co.S2C][co.TIME_LAST_ACK_TCP].total_seconds())

            if initial_sf_ts == float('inf'):
                continue

            # Now store the delta and record connections with handover
            handover_detected = False
            for flow_id, flow in conn.flows.iteritems():
                if handover_detected or co.START not in flow.attr or flow.attr[co.SADDR] in co.IP_PROXY:
                    continue

                max_last_payload = 0 - float('inf')
                if flow.attr[co.C2S].get(co.BYTES, 0) > 0 or flow.attr[co.S2C].get(co.BYTES, 0) > 0:
                    if co.TIME_LAST_ACK_TCP in flow.attr[co.S2C] and flow.attr[co.S2C][co.TIME_LAST_ACK_TCP].total_seconds() > min_last_ack:
                        max_last_payload = max([flow.attr[direction][co.TIME_LAST_PAYLD_TCP].total_seconds() for direction in co.DIRECTIONS])

                # handover_delta = float(flow.attr[co.START]) + max_last_payload - min_last_ack
                handover_delta = max_last_payload - min_last_ack
                if handover_delta > 0.0:
                    # A subflow is used after the last ack of the client seen --> Handover
                    count_handover += 1
                    handover_detected = True

            if handover_detected:
                conn_bytes_tcp = 0
                time_initial_sf = float('inf')
                flow_id_initial_sf = None
                for flow_id, flow in conn.flows.iteritems():
                    if co.START in flow.attr and flow.attr[co.START].total_seconds() < time_initial_sf:
                        time_initial_sf = flow.attr[co.START].total_seconds()
                        flow_id_initial_sf = flow_id

                count_actual_lost_subflows = 0
                for flow_id, flow in conn.flows.iteritems():
                    if co.START in flow.attr and flow.attr[co.START].total_seconds() > 0.0 and flow.attr.get(co.DURATION, 0.0) > 0.0 and co.TIME_FIN_ACK_TCP in flow.attr[co.S2C] and flow.attr[co.S2C][co.TIME_FIN_ACK_TCP].total_seconds() == 0.0:
                        # Only if flow is used
                        if flow.attr[co.C2S].get(co.BYTES, 0) > 0 or flow.attr[co.S2C].get(co.BYTES, 0) > 0:
                            count_actual_lost_subflows += 1

                if len(conn.attr.get(co.ADD_ADDRS, [])) < count_actual_lost_subflows:
                    missing_add_addrs.append((fname, conn_id))

                if len(conn.attr.get(co.RM_ADDRS, [])) < count_actual_lost_subflows:
                    missing_rm_addrs.append((fname, conn_id))

                if len(conn.attr.get(co.ADD_ADDRS, [])) == 0:
                    no_add_addrs.append((fname, conn_id))

                if len(conn.attr.get(co.RM_ADDRS, [])) == 0:
                    no_rm_addrs.append((fname, conn_id))

                if not isinstance(flow_id_initial_sf, int):
                    continue

                # time_second_sf = float('inf')
                # flow_id_second_sf = None
                # for flow_id, flow in conn.flows.iteritems():
                #     if not flow_id == flow_id_initial_sf:
                #         if float(flow.attr.get(co.START, float('inf'))) < time_second_sf:
                #             time_second_sf = float(flow.attr[co.START])
                #             flow_id_second_sf = flow_id
                #
                # if not isinstance(flow_id_second_sf, int):
                #     continue

                nb_conns += 1

                for direction in co.DIRECTIONS:
                    # First count number of total data bytes
                    conn_bytes_tcp = 0
                    for flow_id, flow in conn.flows.iteritems():
                        conn_bytes_tcp += flow.attr[direction].get(co.BYTES, 0)

                    if conn_bytes_tcp <= 0:
                        break

                    nb_bytes[direction] += conn_bytes_tcp

                    bytes_not_initial_sf = 0
                    for flow_id, flow in conn.flows.iteritems():
                        if not flow_id == flow_id_initial_sf:
                            bytes_not_initial_sf += conn.flows[flow_id].attr[direction].get(co.BYTES, 0)
                    # bytes_initial_sfs = bytes_initial_sf + conn.flows[flow_id_second_sf].attr[direction].get(co.BYTES_DATA, 0) + 0.0
                    results[direction][INITIAL_SF].append((bytes_not_initial_sf + 0.0) / conn_bytes_tcp)
                    if (bytes_not_initial_sf + 0.0) / conn_bytes_tcp == 0.0:
                        count_0[direction] += 1
                        print("LOW", (bytes_not_initial_sf + 0.0) / conn_bytes_tcp, bytes_not_initial_sf, conn_bytes_tcp, fname, conn_id)
                    # results[direction][INITIAL_SFS].append((bytes_initial_sfs + 0.0) / conn_bytes_tcp)

base_graph_name = 'not_initial_sf_bytes_handover_'
color = {INITIAL_SF: 'red', INITIAL_SFS: 'blue'}
ls = {INITIAL_SFS: '--', INITIAL_SF: '-'}
for direction in co.DIRECTIONS:
    plt.figure()
    plt.clf()
    fig, ax = plt.subplots()
    graph_fname = os.path.splitext(base_graph_name)[0] + "cdf_" + direction + ".pdf"
    graph_full_path = os.path.join(sums_dir_exp, graph_fname)

    for label in [INITIAL_SF]:
        sample = np.array(sorted(results[direction][label]))
        sorted_array = np.sort(sample)
        yvals = np.arange(len(sorted_array)) / float(len(sorted_array))
        if len(sorted_array) > 0:
            # Add a last point
            sorted_array = np.append(sorted_array, sorted_array[-1])
            yvals = np.append(yvals, 1.0)
            ax.plot(sorted_array, yvals, color=color[label], linestyle=ls[label], linewidth=2, label=label)

            # Shrink current axis's height by 10% on the top
            # box = ax.get_position()
            # ax.set_position([box.x0, box.y0,
            #                  box.width, box.height * 0.9])

            # ax.set_xscale('log')

            # Put a legend above current axis
            # ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.05), fancybox=True, shadow=True, ncol=ncol)
    ax.legend(loc='best')
    plt.xlabel('Fraction of total unique bytes', fontsize=24)
    plt.ylabel("CDF", fontsize=24)
    plt.savefig(graph_full_path)
    plt.close('all')

print("NB CONNS: ", nb_conns)
print("NB BYTES: ", nb_bytes)
print("COUNT 0", count_0)
print(count_handover)
# print("MISSING ADD ADDRS", missing_add_addrs)
# print("MISSING RM ADDRS", missing_rm_addrs)
print("MISSING ADD ADDRS", len(missing_add_addrs))
print("MISSING RM ADDRS", len(missing_rm_addrs))
print("NO ADD ADDRS", len(no_add_addrs))
print("NO RM ADDRS", len(no_rm_addrs))
