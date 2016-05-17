#!/usr/bin/python3

import json
import argparse
import os
import numpy as np
import random
import time
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
        
        self.out_file_name = os.path.join("HAR_files",args['out_file'])
        
        self.timeout = args['timeout']
        
        self.save_headers = args['headers']

        self.max_interval = args['max_interval']
        
        self.browsers_num = args['browsers']

        self.max_requests = args['limit_urls']
    
    def run(self):
        
        # Read URLs and time
        
        in_filename,in_ext=os.path.splitext(self.urls_file)
        
        with open(self.urls_file ,"r") as f:
            
            self.urls=[]
            self.thinking_times=[]
            
            visit_timestamps=[]
            
            history=json.load(f)

        for entry in history:
            self.urls.append(entry["url"])
            visit_timestamps.append(entry["lastVisitTime"])
        
        if not self.max_requests:
            self.max_requests = len(self.urls)

        visit_timestamps.sort()
        
        for i in range(1, len(visit_timestamps)):
            
            think_time=(visit_timestamps[i]-visit_timestamps[i-1])/1000
            
            if think_time<=self.max_interval:
                
                self.thinking_times.append(think_time)
        
        self.cdf, self.inverse_cdf, self.cdf_samples = compute_cdf(self.thinking_times)
        
        print ("Number of URLs: ",len(self.urls))
        
        # Create or clean HARs folder
        
        if not os.path.exists("HAR_files"):
            os.makedirs("HAR_files")
        else:
            for file in os.listdir("HAR_files"):
                
                file_path = os.path.join("HAR_files", file)
                
                if os.path.isfile(file_path):
                    os.remove(file_path)

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
        
        # start queue 
        self.queue = Queue()
        
        try:
            
            self.workers = [Browser(i, self.server,
                                    self.queue, self.timeout, 
                                    self.save_headers, self.out_file_name)
                            for i in range(self.browsers_num)]
            
            for w in self.workers:
                w.start()
            
            number_of_requests = 0
            # Start requesting pages
            for url in self.urls:

                if number_of_requests==self.max_requests:
                    break

                self.queue.put(url)
                number_of_requests += 1
                time.sleep(self.get_thinking_time())
            
            for w in self.workers:
                self.queue.put(None)
            
            for w in self.workers:
                w.join()
                
        except KeyboardInterrupt:
            pass
            
        except Exception as e:
           print("Exception: ", e)
           
        finally:
            self.queue.close()
            self.server.stop()

    def plot_thinking_time_cdf(self):
        
        x = np.linspace(min(self.thinking_times), max(self.thinking_times), num=1000, endpoint=True)
    
        # Plot the cdf
        plt.clf()
        plt.plot(x, self.cdf(x))
        plt.ylim((0,1))
        plt.xlabel("Seconds")
        plt.ylabel("CDF")
        plt.title("Thinking time")
        plt.grid(True)
    
        plt.savefig("Statistics/thinking_time_cdf.png")

    def plot_thinking_time_inverse_cdf(self):
        
        x = np.linspace(min(self.cdf_samples), max(self.cdf_samples), num=1000, endpoint=True)
        
        # Plot the cdf
        plt.clf()
        plt.plot(x, self.inverse_cdf(x))
        plt.ylabel("Seconds")
        plt.xlabel("CDF")
        plt.title("Thinking time")
        plt.grid(True)
    
        plt.savefig("Statistics/thinking_time_inverse_cdf.png")
   
    def get_thinking_time(self):
        
        rand=random.uniform(min(self.cdf_samples),max(self.cdf_samples))
        time = float(self.inverse_cdf(rand))
        return time

if __name__=="__main__":
    
    version="0.1"
    
    parser = argparse.ArgumentParser(description='Web Traffic Generator')
        
    parser.add_argument('--version',action='version',version='%(prog)s '+ version)
    
    parser.add_argument('in_file', metavar='input_file', type=str, 
                       help='History file.')                 
    parser.add_argument('out_file', metavar='output_file', type=str,
                       help='output file name.')
    parser.add_argument('--max-interval', metavar='<max_interval>', type=int, default = 30,
                       help='use statistical intervals with maximum value <max_interval> seconds. Default is 30 sec.')
    parser.add_argument('--timeout', metavar='<timeout>', type=int, default = 30,
                       help='timeout in seconds after declaring failed a visit. Default is 30 sec.')
    parser.add_argument('--headers', action='store_const', const=True, default=False,
                       help='save headers of HTTP requests and responses in Har structs (e.g., to find referer field). Default is False.')
    parser.add_argument('--browsers', metavar='<number>', type=int, default = 3,
                       help='number of browsers to open. Default is 3')
    parser.add_argument('--limit-urls', metavar='<number>', type=int,
                       help='limit requests to <number> urls')
    
    args = vars(parser.parse_args())
    
    WebTrafficGenerator(args).run()

