import os
import json
import time
from multiprocessing import Process

from selenium import webdriver
from selenium.common.exceptions import TimeoutException

class Browser(Process):
    
    def __init__(self, id, proxy_server, urls_queue, hars_queue, timeout,
                 save_headers, temp_dir):
        
        super().__init__()
        
        self.id = id
        self.server = proxy_server
        self.urls_queue = urls_queue
        self.hars_queue = hars_queue
        self.timeout = timeout
        self.save_headers = save_headers
        
        self.temp_dir = temp_dir
    
    '''
    Restart browser and proxy
    '''
    def start_browser(self):
        
        self.proxy = self.server.create_proxy()
        
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
            
            print ("Starting browser:  ", self.id)
            
            self.start_browser()
            
            counter=0
            
            hars=[]
            
            url = self.urls_queue.get()
            
            while url:
                
                counter+=1
                
                self.proxy.new_har(ref=url, options={"captureHeaders": self.save_headers})
                
                print("Browser "+ str(self.id) +": Requesting: ", url)
                
                start_time = time.time()
                
                try:
                    
                    self.driver.get(url)
                    
                except TimeoutException:
                    
                    print ("Browser "+ str(self.id) +": Request timed out")
                    
                    # Restart browser and proxy
                    self.driver.quit()
                    self.proxy.close()
                    self.start_browser()
                    
                else:
                    current_har = self.proxy.har
                
                    current_har["log"]["totalTime"]=(time.time()-start_time)*1000
                
                    hars.append(current_har)
                
                url = self.urls_queue.get()
                
            # Send back HARs
            self.hars_queue.put(hars)

        except KeyboardInterrupt:
            pass
                    
        except Exception as e:
            
            print("Browser ",self.id," - Exception: ", e)
            
            import traceback
            traceback.print_exc()
            
        finally:
            self.urls_queue.close()
            self.hars_queue.close()
            
            self.driver.quit()
            self.proxy.close()
        
        print ("Browser: ", self.id, " processed ", counter, " pages")
