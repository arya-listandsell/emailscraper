from django.shortcuts import render
from App.models import Branch_Name_Model,Websites_Model
from django.http import HttpResponse,JsonResponse,StreamingHttpResponse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time,re,threading,json
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from queue import Queue

# Shared queue for links
link_queue = Queue()
# Set to store collected emails
emails_collected = set()
# Lock for thread-safe access to the email set
email_lock = threading.Lock()
counter_lock = threading.Lock()
email_counter = 0
temp_email_list=[]

############# Scraping for website 3 start #############

def scrape_emails_from_mailto(base_url):
    # Path to ChromeDriver
    chrome_driver_path = r'C:\Users\Admin\Downloads\chromedriver-win64 (1)\chromedriver-win64\chromedriver.exe'
    service = Service(chrome_driver_path)
    driver = webdriver.Chrome(service=service)
    driver.get(base_url)
    time.sleep(3)
    all_emails = set()
    # Function to scroll to the bottom of the page
    def scroll_to_bottom():
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)  # Allow time for content to load
    # Track the previous number of links
    prev_len = 0
    while True:
        # Find and click the 'Load More' button, if available
        try:
            # Find the button by its text containing 'weitere Treffer anzeigen'
            load_more_button = driver.find_element(By.XPATH, "//*[contains(text(), 'weitere Treffer anzeigen')]")
            # Click the button using JavaScript
            driver.execute_script("arguments[0].click();", load_more_button)
            print("Clicked 'Load More' button.")
            time.sleep(3)  # Wait for new content to load
        except Exception as e:
            # If no 'Load More' button is found, break the loop
            print(f"Error: {e}")
            print("No more 'Load More' button found. Breaking loop.")
            break  # Exit the loop if no button is found
        # Scroll to the bottom of the page to ensure all dynamic content is loaded
        scroll_to_bottom()
        # Collect links with the 'todetails' class
        links = driver.find_elements(By.CLASS_NAME, "todetails")
        current_len = len(links)
        print(f"Found {current_len} links with 'todetails' class.")
        # If no new links were found, stop clicking the 'Load More' button
        if current_len == prev_len:
            print("No new links found after clicking 'Load More'. Stopping the process and starting to scrape emails.")
            break  # Exit the loop to start email scraping
        # Update the previous length of links
        prev_len = current_len
    # After all the scrolling and clicking, collect links with the 'todetails' class
    hrefs = [link.get_attribute("href") for link in links if link.get_attribute("href")]
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?<!png)(?<!we)(?<!web)(?<!pn)(?<!webp)'
    # Extract emails from each link's page
    for href in hrefs:
        try:
            print(f"Navigating to {href}")
            driver.get(href)
            time.sleep(10) 
            page_source = driver.page_source
            emails = re.findall(email_pattern, page_source)
            all_emails.update(emails)
        except Exception as e:
            print(f"Error navigating to {href}: {e}")
    driver.quit()
    print(f"Total {len(all_emails)} emails found.")
    return all_emails

############# Scraping for website 3 end #############


############# Scraping for website 2 start #############

def get_headless_driver():
    CHROME_DRIVER_PATH = r'C:\Users\Admin\Downloads\chromedriver-win64 (1)\chromedriver-win64\chromedriver.exe'
    """Configure and return a headless Chrome WebDriver."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--disable-webgl")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.page_load_strategy = 'eager'
    service = Service(CHROME_DRIVER_PATH, service_args=["--verbose"], log_path="nul")  # Windows users
    return webdriver.Chrome(service=service, options=chrome_options)

def collect_links(base_url):
    """Collect links and add them to the shared queue while scrapers are running."""
    driver = get_headless_driver()
    driver.get(base_url)
    time.sleep(2)
    def scroll_to_bottom():
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
    links = set()
    prev_len = 0
    while True:
        try:
            load_more_button = driver.find_element(By.XPATH, "//*[contains(text(), 'Mehr Anzeigen')]")
            driver.execute_script("arguments[0].click();", load_more_button)
            print("Clicked 'Load More' button.")
            time.sleep(2)
        except Exception:
            print("No 'Load More' button found.")
        scroll_to_bottom()
        articles = driver.find_elements(By.CSS_SELECTOR, ".mod.mod-Treffer")
        print(f"Found {len(articles)} articles.")
        for article in articles:
            a_tags = article.find_elements(By.TAG_NAME, "a")
            for a_tag in a_tags:
                href = a_tag.get_attribute("href")
                if href and href not in links:
                    links.add(href)
                    link_queue.put(href)  # Add link to the queue
                    print(f"Link added to queue: {href}")

        if len(links) == prev_len:
            print("No new links found. Stopping collection.")
            break
        prev_len = len(links)
    # Add sentinel values to indicate no more links will be added
    for _ in range(20):  # Number of extractor threads
        link_queue.put(None)
    driver.quit()
    print("Link collection complete.")

def extract_emails():
    """Extract emails from the links in the link queue."""
    global email_counter
    driver = get_headless_driver()  # Create WebDriver once per thread
    while True:
        href = link_queue.get()
        if href is None:  # Sentinel value
            link_queue.task_done()
            break
        try:
            driver.get(href)
            time.sleep(2)
            email_div = driver.find_element(By.ID, "email_versenden")
            data_link = email_div.get_attribute("data-link")
            if data_link and 'mailto:' in data_link:
                email = data_link.split("mailto:")[1].split("?")[0]
                with email_lock:
                    if email not in emails_collected:
                        emails_collected.add(email)
                        with counter_lock:
                            email_counter += 1
                        print(f"Extracted email #{email_counter}: {email}")
                        temp_email_list.append(email)
        except Exception as e:
            print(f"Error processing link {href}: {e}")
        finally:
            link_queue.task_done()
            
    driver.quit()  # Quit WebDriver when thread ends





def scrape_emails_from_todetails(base_url):
    # Start the link collector thread
    collector_thread = threading.Thread(target=collect_links, args=(base_url,))
    collector_thread.start()
    # Start multiple email extractor threads
    extractor_threads = []
    for _ in range(20):  # Number of concurrent email extractor threads
        thread = threading.Thread(target=extract_emails)
        thread.start()
        extractor_threads.append(thread)
    # Wait for the link collector to finish
    collector_thread.join()

    # Wait for all extractor threads to finish
    for thread in extractor_threads:
        thread.join()
    # Save the collected emails
    return emails_collected





############# Scraping for website 2 end #############



############# Scraping for website 1 Start ############# 


def extract_emails(page_content):
    email_pattern =  r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?<!png)(?<!we)(?<!web)(?<!pn)(?<!webp)'
    return set(re.findall(email_pattern, page_content))

def get_inner_links(page_content, base_url): 
    soup = BeautifulSoup(page_content, 'html.parser')
    links = soup.find_all('a', href=True)
    inner_links = set()
    for link in links:
        href = link['href']
        if href.startswith('/'):
            inner_links.add(base_url + href)
        elif base_url in href:
            inner_links.add(href)
    return inner_links

def scrape_emails_from_site(driver, outer_url):
    driver.get(outer_url)
    time.sleep(3)  # Let the page load

    emails = set()

    while True:
        # Extract emails from the current page
        outer_page_content = driver.page_source
        emails.update(extract_emails(outer_page_content))

        # Extract and process inner links
        inner_links = get_inner_links(outer_page_content, outer_url)
        for link in inner_links:
            try:
                driver.get(link)
                time.sleep(2)  # Let the inner page load
                inner_page_content = driver.page_source
                emails.update(extract_emails(inner_page_content))
            except Exception as e:
                print(f"Error processing link {link}: {e}")
                continue

        # Wait and click the "Next" button if available
        try:
            print('in try block')
            next_button = driver.find_element(By.CLASS_NAME, 'link.icon-right')
            ActionChains(driver).move_to_element(next_button).click(next_button).perform()
            print('next button clicked')
            time.sleep(3)  # Wait for the next page to load
        except Exception as e:
            print("No more pages or error navigating to the next page:", e)
            break
    print(len(emails))
    for email in emails:
        print(email)

############# Scraping for website 1 End #############

#loading page
def form_request(request):
    website_name = Websites_Model.objects.all()
    return render(request, 'form.html',{'website_name':website_name})


#branch name fetching
def branch_name_autocomplete(request):
    query = request.GET.get('term', '')
    branches = Branch_Name_Model.objects.filter(branch_name__icontains=query)
    branch_names = [branch.branch_name for branch in branches]
    return JsonResponse(branch_names, safe=False)


# email fetching main
def fetch_emails(request):
    website = int(request.GET.get('websitename', '').strip())
    branchname = request.GET.get('branchname', '').strip()
    cityname = request.GET.get('cityname', '').strip()
    
    if website == 1:
        driver_service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=driver_service)
        try:
            outer_url = f"https://www.11880.com/suche/{branchname}/{cityname}"
            scrape_emails_from_site(driver, outer_url)
        finally:
            driver.quit()
    elif website == 2:
        try:
            base_url = f"https://www.gelbeseiten.de/suche/{branchname}/{cityname}"
            start_time = time.time()
            emails_available = scrape_emails_from_todetails(base_url)
            end_time = time.time()
            print(f"Process completed in {end_time - start_time:.2f} seconds.")
        except Exception as e:
            return('No more pages or error navigating to the next page:',e)
        return JsonResponse(list(emails_available), safe=False)
            
    elif website == 3:
        try:
            base_url = f"https://www.dastelefonbuch.de/Suche/{branchname}/{cityname}"
            emails = scrape_emails_from_mailto(base_url)
            print('Emails Available',emails)
        except Exception as e:
            return('No more pages or error navigating to the next page:',e)
        return JsonResponse(list(emails), safe=False) 
    return HttpResponse()







