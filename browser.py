import os
import json
import time
from multiprocessing import Process

from selenium import webdriver
from selenium.common.exceptions import TimeoutException

class Browser(Process):
    
    def __init__(self, id, proxy_server, urls_queue, hars_queue, timeout, save_headers):
        
        super().__init__()
        
        self.id = id
        self.server = proxy_server
        self.urls_queue = urls_queue
        self.hars_queue = hars_queue
        self.timeout = timeout
        self.save_headers = save_headers
        
    def run(self):
        
        print ("Starting browser:  ", self.id)
        
        self.proxy = self.server.create_proxy()
        
        self.profile = webdriver.FirefoxProfile()
        
        self.profile.set_proxy(self.proxy.selenium_proxy())

        self.driver = webdriver.Firefox(firefox_profile=self.profile)
        self.driver.set_page_load_timeout(self.timeout)
        
        counter=0
        
        try:
            
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
            self.proxy.close()
            self.driver.quit()
        
        print ("Browser: ", self.id, " processed ", counter, " pages")
