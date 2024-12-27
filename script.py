import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException

from pymongo import MongoClient
import time
import uuid
from datetime import datetime
import requests
import json


# Constants
BROWSER_BINARY_PATH = "Your Browser Path"
MONGO_URI = 'Your MongoDB URI'
TWITTER_LOGIN_URL = 'https://x.com/i/flow/login'
PROXYMESH_URL = 'Not Configured'
USERNAME = 'Your Twitter Username'
PASSWORD = 'Your Twitter Password'
CHROME_DRIVER_PATH = "Your chrome driver path" #Download here: https://storage.googleapis.com/chrome-for-testing-public/131.0.6778.204/win32/chromedriver-win32.zip
EMAIL = 'Your Twitter Email Address'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def setup_driver():
    try:
        options = webdriver.ChromeOptions()
        options.binary_location = BROWSER_BINARY_PATH
        logging.info("Driver setup complete.")
        return webdriver.Chrome(service=Service(CHROME_DRIVER_PATH), options=options)
    except Exception as e:
        logging.error(f"Error setting up WebDriver: {e}")
        raise


def fetch_trending_topics():
    driver = setup_driver()
    try:
        driver.get(TWITTER_LOGIN_URL)
        time.sleep(10)

        driver.find_element(By.CLASS_NAME, "r-30o5oe").send_keys(USERNAME + Keys.RETURN)
        time.sleep(2)
        
        wait = WebDriverWait(driver, 10)
        try:
            email_or_phone_field = wait.until(EC.presence_of_element_located((By.NAME, "text")))
            email_or_phone_field.send_keys(EMAIL + Keys.RETURN)
            time.sleep(2)
        except:
            logging.info("No email/phone prompt detected, proceeding to password entry.")

        password_field = wait.until(EC.presence_of_element_located((By.NAME, "password")))
        password_field.send_keys(PASSWORD + Keys.RETURN)
        time.sleep(10)

        
        classes_to_target = [
            "css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3"
        ]
        
        xpath_query = ".//div[@dir='ltr' and not(@class='css-146c3p1') ]//span[" + " or ".join(
             [f"contains(@class, '{class_name}')" for class_name in classes_to_target]
        ) + "]"
        retries = 3
        for attempt in range(retries):
            try:
                section = wait.until(EC.presence_of_element_located((By.XPATH, "//section[@aria-labelledby='accessible-list-1']")))  
                trending_elements = section.find_elements(By.XPATH, xpath_query)
                trending_topics = [element.text for element in trending_elements if element.text.strip()]
                
                unwanted_topics = ["What’s happening", "Trending in India","Show more"]
                trending_topics = [topic for topic in trending_topics if topic not in unwanted_topics]
                break  
            except StaleElementReferenceException as e:
                logging.warning(f"Attempt {attempt + 1} - Stale element exception: {e}")
                if attempt == retries - 1:
                    raise
                time.sleep(2)

        ip_address = requests.get("http://ipinfo.io/ip").text.strip()
    finally:
        driver.quit()

    return trending_topics, ip_address


def save_to_mongo(trending_topics, ip_address):
    try:
        logging.info("Connecting to MongoDB...")
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.server_info()  
        logging.info("Connected to MongoDB successfully.")
        
        db = client.twitter_trends
        collection = db.trends
        
        data = {
            "unique_id": str(uuid.uuid4()),
            "trending_topics": trending_topics,
            "date_time": datetime.now().isoformat(),
            "ip_address": ip_address,
        }
        
        logging.info("Attempting to save data to MongoDB...")
        collection.insert_one(data)
        logging.info("Data saved to MongoDB successfully.")
        
    except Exception as e:
        logging.error(f"Error saving data to MongoDB: {e}")



def fetch_trending_data_from_mongo():
    try:
        logging.info("Connecting to MongoDB...")
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.server_info() 
        logging.info("Connected to MongoDB successfully.")

        db = client.twitter_trends
        collection = db.trends

        trending_data = collection.find().sort([("date_time", -1)])  

        return trending_data
    except Exception as e:
        logging.error(f"Error fetching data from MongoDB: {e}")
        return []


def process_trending_data(trending_data):
    trending_json = {"trending_topics": []}

    for entry in trending_data:
        trending_topics = entry.get("trending_topics", [])
        
        current_category = None
        for i, item in enumerate(trending_topics):
            if "· Trending" in item: 
                current_category = item.split(" · ")[0]
            elif "posts" in item and current_category:  
                topic_data = {
                    "category": current_category,
                    "topic": trending_topics[i - 1] if i - 1 >= 0 else "Unknown",  
                    "post_count": item  
                }
                trending_json["trending_topics"].append(topic_data)
    
    return trending_json

# Main execution
if __name__ == "__main__":
    trending_topics, ip_address = fetch_trending_topics()
    if trending_topics:
        save_to_mongo(trending_topics, ip_address)

    trending_data_from_db = fetch_trending_data_from_mongo()

    if trending_data_from_db:
        trending_json = process_trending_data(trending_data_from_db)
        print(json.dumps(trending_json, indent=2))
    else:
        print("No data available to process.")
