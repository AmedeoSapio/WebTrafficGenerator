import os
import json
from multiprocessing import Process

from selenium import webdriver
from selenium.common.exceptions import TimeoutException

class Browser(Process):
    
    def __init__(self, id, proxy_server, queue, timeout, save_headers,
                 out_file_name):
        
        super().__init__()
        
        self.id = id
        self.server = proxy_server
        self.queue = queue
        self.timeout = timeout
        self.save_headers = save_headers
        
        filename,ext=os.path.splitext(out_file_name)
        self.out_file = filename+str(id)+ext
        
    def run(self):
        
        print ("Starting browser:  ", self.id)
        
        self.proxy = self.server.create_proxy()
        
        self.profile = webdriver.FirefoxProfile()
        
        self.profile.set_proxy(self.proxy.selenium_proxy())

        self.driver = webdriver.Firefox(firefox_profile=self.profile)
        self.driver.set_page_load_timeout(self.timeout)
        
        counter=0
        
        try:
            
            with open(self.out_file,"a") as f:
                
                url = self.queue.get()
                
                while url:
                    
                    counter+=1
                    
                    self.proxy.new_har(ref=url, options={"captureHeaders": self.save_headers})
                    
                    print("Requesting: ", url)
                    
                    try:
                        
                        self.driver.get(url)
                        
                    except TimeoutException:
                        print ("Request timed out")
                    
                    json.dump(self.proxy.har,f)
                    
                    url = self.queue.get()
        
        except KeyboardInterrupt:
            pass
                    
        except Exception as e:
            
            print("Exception: ", e)
            
        finally:
            self.queue.close()
            self.proxy.close()
            self.driver.quit()
        
        print ("Browser: ", self.id, " processed ", counter, " pages")
