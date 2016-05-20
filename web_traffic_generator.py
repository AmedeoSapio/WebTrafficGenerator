#!/usr/bin/python3

import json
import argparse
import os
import numpy as np
import random
import time
import tempfile
import matplotlib.pyplot as plt
from multiprocessing import Queue, cpu_count

from browsermobproxy import Server
from selenium import webdriver
from selenium.common.exceptions import TimeoutException

from browser import Browser
from utils import *

class WebTrafficGenerator:
    
    def __init__(self,args):
        
        self.browser_mob_proxy_location = os.environ.get("BROWSERMOBPROXY_BIN")
        
        if not self.browser_mob_proxy_location:
            self.browser_mob_proxy_location = "./browsermob-proxy/bin/browsermob-proxy"
        
        # Parse arguments
        self.urls_file = args['in_file']
        
        self.out_file_name = args['out_file']
        
        self.timeout = args['timeout']
        
        self.save_headers = args['headers']

        self.max_interval = args['max_interval']
        
        self.browsers_num = args['browsers']

        self.max_requests = args['limit_urls']
        
        self.no_sleep = args['no_sleep']
        
    def run(self):
        
        # create temporary directory for downloads
        self.temp_dir = tempfile.TemporaryDirectory()
        
        try:
            
            # Read URLs and time
            
            self.urls=[]
            self.thinking_times=[]
            
            visit_timestamps=[]
            
            with open(self.urls_file ,"r") as f:
                
                history = f.read().splitlines()
    
            for line in history:
                
                entry = line.split()
                
                if not (entry[1].lower().startswith("file://") or
                    (entry[1].lower().startswith("http://") and 
                     (entry[1].lower().startswith("10.",7) or 
                      entry[1].lower().startswith("192.168.",7))) or 
                    (entry[1].lower().startswith("https://") and 
                     (entry[1].lower().startswith("10.",8) or 
                      entry[1].lower().startswith("192.168.",8)))):
                    
                    # convert timestamp in seconds
                    visit_timestamps.append(float(entry[0])/1000000)
                    
                    self.urls.append(entry[1])
            
            if not self.max_requests:
                self.max_requests = len(self.urls)
    
            visit_timestamps.sort()
            
            for i in range(1, len(visit_timestamps)):
                
                think_time=(visit_timestamps[i]-visit_timestamps[i-1])
                
                if think_time<=self.max_interval:
                    
                    self.thinking_times.append(think_time)
            
            self.cdf, self.inverse_cdf, self.cdf_samples = compute_cdf(self.thinking_times)
            
            print ("Number of URLs: ",len(self.urls))
            
            # Create or clean statistics folder
            
            if not os.path.exists("Statistics"):
                os.makedirs("Statistics")
            else:
                for file in os.listdir("Statistics"):
                    
                    file_path = os.path.join("Statistics", file)
                    
                    if os.path.isfile(file_path):
                        os.remove(file_path)
    
            # Plot history statistics
            self.plot_thinking_time_cdf()
            self.plot_thinking_time_inverse_cdf()
            
            # Start Proxy
            self.server = Server(self.browser_mob_proxy_location)
            
            self.server.start()
            
            # start queues
            self.urls_queue = Queue()
            self.hars_queue = Queue()
            
            try:
                
                self.workers = [Browser(i, self.server,
                                        self.urls_queue, self.hars_queue,
                                        self.timeout, self.save_headers,
                                        self.temp_dir.name)
                                for i in range(self.browsers_num)]
                
                for w in self.workers:
                    w.start()
                
                number_of_requests = 0
                # Start requesting pages
                for url in self.urls:
    
                    if number_of_requests==self.max_requests:
                        break
    
                    self.urls_queue.put(url)
                    number_of_requests += 1
                    
                    if not self.no_sleep:
                        time.sleep(self.get_thinking_time())
                
                for w in self.workers:
                    self.urls_queue.put(None)
                
                self.hars = []
                
                for w in self.workers:
                    browser_hars = self.hars_queue.get()
                    self.hars.extend(browser_hars)
                
                # write HAR file
                with open(self.out_file_name,"w") as f:
                    json.dump(self.hars,f)
                
                # Gather statistics
                self.stats = {
                              "totalTime":[],
                              "blocked":[],
                              "dns":[],
                              "connect":[],
                              "send":[],
                              "wait":[],
                              "receive":[]
                              }
                
                for har in self.hars:
                    
                    if har["log"]["totalTime"]!=-1:
                        self.stats["totalTime"].append(har["log"]["totalTime"])
                    
                    for entry in har["log"]["entries"]:
                        
                        # Queuing
                        if entry["timings"]["blocked"]!=-1:
                            self.stats["blocked"].append(entry["timings"]["blocked"])
                            
                        # DNS resolution
                        if entry["timings"]["dns"]!=-1:
                            self.stats["dns"].append(entry["timings"]["dns"])
                            
                        # TCP Connection
                        if entry["timings"]["connect"]!=-1:
                            self.stats["connect"].append(entry["timings"]["connect"])
                            
                        # HTTP Request send
                        if entry["timings"]["send"]!=-1:
                            self.stats["send"].append(entry["timings"]["send"])
                            
                        # Wait the server
                        if entry["timings"]["wait"]!=-1:
                            self.stats["wait"].append(entry["timings"]["wait"])
                            
                        # HTTP Response receive
                        if entry["timings"]["receive"]!=-1:
                            self.stats["receive"].append(entry["timings"]["receive"])
                        
                # Save statistics
                self.plot_stats()
                
                for w in self.workers:
                    w.join()
                    
            except KeyboardInterrupt:
                pass
            
            finally:
                self.urls_queue.close()
                self.hars_queue.close()
                self.server.stop()
                
        except Exception as e:
           print("Exception: ", e)
           
           import traceback
           traceback.print_exc()
           
        finally:
            
            self.temp_dir.cleanup()

    def plot_thinking_time_cdf(self):
        
        x = np.linspace(min(self.thinking_times), max(self.thinking_times), num=10000, endpoint=True)
    
        # Plot the cdf
        fig = plt.figure()
        axes = fig.add_subplot(111)
        axes.plot(x, self.cdf(x))
        axes.set_ylim((0,1))
        axes.set_xlabel("Seconds")
        axes.set_ylabel("CDF")
        axes.set_title("Thinking time")
        axes.grid(True)
    
        fig.savefig(os.path.join("Statistics","thinking_time_cdf.png"))

    def plot_thinking_time_inverse_cdf(self):
        
        x = np.linspace(min(self.cdf_samples), max(self.cdf_samples), num=10000, endpoint=True)
        
        # Plot the cdf
        fig = plt.figure()
        axes = fig.add_subplot(111)
        axes.plot(x, self.inverse_cdf(x))
        axes.set_xlim((0,1))
        axes.set_ylabel("Seconds")
        axes.set_xlabel("CDF")
        axes.set_title("Thinking time")
        axes.grid(True)
    
        fig.savefig(os.path.join("Statistics","thinking_time_inverse_cdf.png"))
   
    def get_thinking_time(self):
        
        rand=random.uniform(min(self.cdf_samples),max(self.cdf_samples))
        time = float(self.inverse_cdf(rand))
        return time
    
    def plot_stats(self):
        
        fig_total = plt.figure()
        axes_total = fig_total.add_subplot(111)
        
        fig_timings = plt.figure()
        axes_timings = fig_timings.add_subplot(1,1,1)
        
        fig_timings_log = plt.figure()
        axes_timings_log = fig_timings_log.add_subplot(1,1,1)
        
        for key in self.stats:
            if len(set(self.stats[key]))>1:
                cdf = compute_cdf(self.stats[key])
                
                x = np.linspace(min(self.stats[key]), max(self.stats[key]), num=10000, endpoint=True)
            
                # Plot the cdf
                if key=="totalTime":
                    axes_total.plot(x/1000, cdf[0](x), label=key)
                else:
                    axes_timings.plot(x, cdf[0](x), label=key)
                    
                    # zero is not valid with log axes
                    if min(self.stats[key])==0:
                        non_zero_min = find_non_zero_min(self.stats[key])
                        
                        if non_zero_min == 0:
                            continue
                        
                        x = np.linspace(non_zero_min, max(self.stats[key]), num=10000, endpoint=True)
                        
                    axes_timings_log.plot(x, cdf[0](x), label=key)
                
        axes_total.set_ylim((0,1))
        axes_total.set_xlabel("Seconds")
        axes_total.set_ylabel("CDF")
        axes_total.set_title("Page load time")
        axes_total.grid(True)
        
        fig_total.savefig(os.path.join("Statistics","page_load_cdf.png"))
        
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
        axes_timings_log.grid(True)
        axes_timings_log.legend(loc='best')
    
        fig_timings.savefig(os.path.join("Statistics","timings_cdf.png"))
        fig_timings_log.savefig(os.path.join("Statistics","timings_cdf_log.png"))
        
if __name__=="__main__":
    
    version="0.1"
    
    parser = argparse.ArgumentParser(description='Web Traffic Generator')
        
    parser.add_argument('--version',action='version',version='%(prog)s '+ version)
    
    parser.add_argument('in_file', metavar='input_file', type=str, 
                       help='History file.')                 
    parser.add_argument('out_file', metavar='output_file', type=str,
                       help='output HAR file name.')
    parser.add_argument('--max-interval', metavar='<max_interval>', type=int, default = 30,
                       help='use statistical intervals with maximum value <max_interval> seconds. Default is 30 sec.')
    parser.add_argument('--timeout', metavar='<timeout>', type=int, default = 30,
                       help='timeout in seconds after declaring failed a visit. Default is 30 sec.')
    parser.add_argument('--headers', action='store_const', const=True, default=False,
                       help='save headers of HTTP requests and responses in Har structs (e.g., to find referer field). Default is False.')
    parser.add_argument('--no-sleep', action='store_const', const=True, default=False,
                       help='Do not sleep between requests. Default is False.')
    parser.add_argument('--browsers', metavar='<number>', type=int, default = 3,
                       help='number of browsers to open. Default is 3')
    parser.add_argument('--limit-urls', metavar='<number>', type=int,
                       help='limit requests to <number> urls')
    
    args = vars(parser.parse_args())
    
    WebTrafficGenerator(args).run()

