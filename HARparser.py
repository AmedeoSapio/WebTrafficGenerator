#!/usr/bin/python3

import json
import argparse
import os
import matplotlib.pyplot as plt

from utils import *

def parse_hars(hars, no_https):
    
    # Gather statistics
    stats = {
             "totalTime":[],
             "blocked":[],
             "dns":[],
             "connect":[],
             "send":[],
             "wait":[],
             "receive":[]
             }
    
    for har in hars:
        
        if har["log"]["totalTime"]!=-1:
            stats["totalTime"].append(har["log"]["totalTime"])
        
            for entry in har["log"]["entries"]:
                
                if ((not no_https or not entry["request"]["url"].lower().startswith("https://")) and
                    not "_error" in entry["response"]):
                
                    # Queuing
                    if entry["timings"]["blocked"]!=-1:
                        stats["blocked"].append(entry["timings"]["blocked"])
                        
                    # DNS resolution
                    if entry["timings"]["dns"]!=-1:
                        stats["dns"].append(entry["timings"]["dns"])
                        
                    # TCP Connection
                    if entry["timings"]["connect"]!=-1:
                        stats["connect"].append(entry["timings"]["connect"])
                        
                    # HTTP Request send
                    if entry["timings"]["send"]!=-1:
                        stats["send"].append(entry["timings"]["send"])
                        
                    # Wait the server
                    if entry["timings"]["wait"]!=-1:
                        stats["wait"].append(entry["timings"]["wait"])
                        
                    # HTTP Response receive
                    if entry["timings"]["receive"]!=-1:
                        stats["receive"].append(entry["timings"]["receive"])
                        
    return stats
                
def plot_stats(stats, out_folder):
    
    fig_total = plt.figure()
    axes_total = fig_total.add_subplot(111)
    
    fig_timings = plt.figure()
    axes_timings = fig_timings.add_subplot(1,1,1)
    
    fig_timings_log = plt.figure()
    axes_timings_log = fig_timings_log.add_subplot(1,1,1)
    
    for key in stats:
        if len(set(stats[key]))>1:
            cdf = compute_cdf(stats[key])
            
            x = np.linspace(min(stats[key]), max(stats[key]), num=10000, endpoint=True)
        
            # Plot the cdf
            if key=="totalTime":
                axes_total.plot(x/1000, cdf[0](x), label=key)
            else:
                
                if key=="dns":
                    color="#6b6b6b"
                elif key=="connect":
                    color="#ff1494"
                elif key=="send":
                    color="#66cc00"
                elif key=="wait":
                    color="#ff8c00"
                elif key=="receive":
                    color="#1f8fff"
                else:
                    color=None
                
                axes_timings.plot(x, cdf[0](x), label=key, color=color)
                
                # zero is not valid with log axes
                if min(stats[key])==0:
                    non_zero_min = find_non_zero_min(stats[key])
                    
                    if non_zero_min == 0:
                        continue
                    
                    x = np.linspace(non_zero_min, max(stats[key]), num=10000, endpoint=True)
                    
                axes_timings_log.plot(x, cdf[0](x), label=key, color=color)
            
    axes_total.set_ylim((0,1))
    axes_total.set_xlabel("Seconds")
    axes_total.set_ylabel("CDF")
    axes_total.set_xscale("log")
    axes_total.set_title("Page load time")
    axes_total.grid(True, which="both", axis="x")
    axes_total.grid(True, which="major", axis="y")
    
    fig_total.savefig(os.path.join(out_folder,"page_load_cdf.png"))
    
    axes_timings.set_ylim((0,1))
    axes_timings.set_xlabel("Milliseconds")
    axes_timings.set_ylabel("CDF")
    axes_timings.set_title("Single resource timings")
    axes_timings.grid(True)
    axes_timings.legend(loc='best')
    
    axes_timings_log.set_ylim((0,1))
    axes_timings_log.set_xlabel("Milliseconds")
    axes_timings_log.set_ylabel("CDF")
    axes_timings_log.set_xscale("log")
    axes_timings_log.set_title("Single resource timings")
    axes_timings_log.grid(True, which="both", axis="x")
    axes_timings_log.grid(True, which="major", axis="y")
    
    axes_timings_log.legend(loc='best')
    
    fig_timings.savefig(os.path.join(out_folder,"timings_cdf.png"))
    fig_timings_log.savefig(os.path.join(out_folder,"timings_cdf_log.png"))
    
if __name__=="__main__":
    
    version="0.1"
    
    parser = argparse.ArgumentParser(description='HTTP Archive parser')
        
    parser.add_argument('--version',action='version',version='%(prog)s '+ version)
    
    parser.add_argument('input', metavar='input', type=str, 
                       help='HAR file, or folder with HAR files.')
    parser.add_argument('out_folder', metavar='output_folder', type=str,
                       help='output statistics folder name.')
    parser.add_argument('--no-https', action='store_const', const=True, default=False,
                       help='do not plot requests on https.')
    
    args = vars(parser.parse_args())
    
    # Parse arguments
    har_file = args['input']
    
    out_folder = args['out_folder']
    
    no_https = args['no_https']

    hars = []
    
    if os.path.isdir(har_file):
        for file in os.listdir(har_file):
                    
            file_path = os.path.join(har_file, file)
            
            with open(file_path,"r") as f:
                hars.extend(json.load(f))
    
    elif os.path.isfile(har_file):
        
        with open(har_file,"r") as f:
                hars.extend(json.load(f))
    
    else:
        print ("Invalid input: " + har_file)
        exit()
        
    if not os.path.exists(out_folder):
        os.makedirs(out_folder)
    
    print("Pages requested: ",len(hars))
    
    stats = parse_hars(hars,no_https)
    
    with open(os.path.join(out_folder,"stats.json"),"w") as f:
        json.dump(stats,f)
    
    # Save statistics
    plot_stats(stats, out_folder)
