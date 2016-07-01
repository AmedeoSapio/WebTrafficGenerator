import os
import json
import time
import errno

from socket import error as socket_error
from multiprocessing import Process

from selenium import webdriver
from selenium.common.exceptions import TimeoutException

class Browser(Process):
    
    def __init__(self, id, proxy_server, urls_queue, hars_queue, barrier,
                 timeout, save_headers, temp_dir):
        
        super().__init__()
        
        self.id = id
        self.server = proxy_server
        self.urls_queue = urls_queue
        self.hars_queue = hars_queue
        self.barrier = barrier
        self.timeout = timeout
        self.save_headers = save_headers
        
        self.temp_dir = temp_dir
    
    '''
    Restart browser and proxy
    '''
    def start_browser(self):
        
        try:
            self.proxy = self.server.create_proxy()
        except Exception as e:
            print("Browser "+ str(self.id) +": Proxy server is offline: ", e)
            
            try:
                self.barrier.wait(3*self.timeout)
            except BrokenBarrierError: 
                print("Browser "+ str(self.id) +": Timed out waiting for a browser", e)
                exit(1)
            
            self.proxy = self.server.create_proxy()
            
        
        self.proxy.timeouts = {
                               'request': 5,
                               'read': 5,
                               'connection': 5,
                               'dns': 5
        } 
        
        self.profile = webdriver.FirefoxProfile()
        
        # Download files
        self.profile.set_preference("browser.download.folderList", 2)
        self.profile.set_preference("browser.download.dir", self.temp_dir)
        
        # A comma-separated list of MIME types to save to disk without asking
        # what to use to open the file
        self.profile.set_preference("browser.helperApps.neverAsk.saveToDisk",
                                    "application/x-msexcel,"+
                                    "application/excel,"+
                                    "application/x-excel,"+
                                    "application/vnd.ms-excel,"+
                                    "application/pdf,"+
                                    "application/msword,"+
                                    "application/xml,"+
                                    "application/octet-stream,"+
                                    "image/png,"+
                                    "image/jpeg,"+
                                    "text/html,"+
                                    "text/plain,"+
                                    "text/csv")
                                    
        # Do not show the Download Manager                  
        self.profile.set_preference("browser.download.manager.showWhenStarting", False)
        self.profile.set_preference("browser.download.manager.focusWhenStarting", False)
        self.profile.set_preference("browser.download.manager.useWindow", False)
        self.profile.set_preference("browser.download.manager.showAlertOnComplete", False)
        self.profile.set_preference("browser.download.manager.closeWhenDone", False)
        
        # Do not ask what to do with an unknown MIME type
        self.profile.set_preference("browser.helperApps.alwaysAsk.force", False)
        
        self.profile.set_proxy(self.proxy.selenium_proxy())
        
        self.driver = webdriver.Firefox(firefox_profile=self.profile)
        
        self.driver.set_page_load_timeout(self.timeout)
        
    def run(self):
        
        try:
            
            print ("Starting browser: "+ str(self.id))
            
            self.start_browser()
            
            counter=0
            
            hars=[]
            
            url = self.urls_queue.get()
            
            while url:
                
                counter+=1
                
                try:
                    
                    self.proxy.new_har(ref=url, options={"captureHeaders": self.save_headers})
                    
                    print("Browser "+ str(self.id) +": ", url)
                    
                    start_time = time.time()
                    
                    self.driver.get(url)
                    
                    total_time = (time.time()-start_time)*1000
                    
                    current_har = self.proxy.har
                
                    current_har["log"]["totalTime"] = total_time
                
                    hars.append(current_har)
                    
                except Exception as e:
                    
                    if isinstance(e, TimeoutException):
                        
                        print ("Browser "+ str(self.id) +": Request timed out")
                    
                    elif isinstance(e, socket_error):
                        if e.errno == errno.ECONNREFUSED:
                            print ("Browser "+ str(self.id) +": Proxy offline")
                        else:
                            print ("Browser "+ str(self.id) +": Proxy error")
                    else: 
                        
                        print("Browser "+ str(self.id) +": Exception: ", e)
                        
                    # Restart browser and proxy
                    
                    try:
                        self.driver.quit()
                    except:
                        print("Browser "+ str(self.id) +": - Unable to close the browser: ", e)
                    
                    try:
                        self.proxy.close()
                    except:
                        print("Browser "+ str(self.id) +": - Unable to close the proxy: ", e)
                    
                    self.start_browser()
                
                url = self.urls_queue.get()

        except KeyboardInterrupt:
            pass
                    
        except Exception as e:
            
            print("Browser "+ str(self.id) +": Exception: ", e)
            
            import traceback
            traceback.print_exc()
            
        finally:
            # Send back HARs
            self.hars_queue.put(hars)
            
            self.urls_queue.close()
            self.hars_queue.close()
            
            try:
                self.driver.quit()
            except AttributeError:
                pass
            
            try:
                self.proxy.close()
            except:
                pass
        
        print ("Browser "+ str(self.id) +": processed ", counter, " pages")
