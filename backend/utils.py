import requests
import os
from urllib.parse import urlparse, unquote
from logger import logger
import tempfile
import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from config import PATHS

logger = logging.getLogger(__name__)

def get_pdf_link_only(year, district, police_station, fir_number):
    """
    Retrieves the PDF URL after performing a form search on the website.
    Returns the expected file path where the PDF should be saved.
    """
    logger.info(f"Starting PDF retrieval for FIR: year={year}, district={district}, police_station={police_station}, fir_number={fir_number}")
    
    year = str(year)
    fir_number = str(fir_number)
    url = "https://haryanapolice.gov.in/ViewFIR/FIRStatusSearch?From=LFhlihlx/W49VSlBvdGc4w=="
    download_dir = PATHS["downloads"]
    
    logger.info(f"Creating download directory: {download_dir}")
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
        logger.debug("Download directory created successfully")
    
    expected_file_path = os.path.join(download_dir, f"{fir_number}-{year}-{district}-{police_station}.pdf")
    logger.info(f"Expected file path: {expected_file_path}")
    
    logger.debug("Configuring Chrome options")
    chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    temp_user_data_dir = tempfile.mkdtemp()
    logger.debug(f"Created temporary user data directory: {temp_user_data_dir}")
    chrome_options.add_argument(f"--user-data-dir={temp_user_data_dir}")
    
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    max_retries = 1  # Increased retries
    
    for attempt in range(max_retries):
        driver = None
        try:
            logger.info(f"Starting attempt {attempt + 1}/{max_retries}")
            driver = webdriver.Chrome(options=chrome_options)
            logger.debug("Chrome WebDriver initialized successfully")
            
            logger.debug(f"Setting page load timeout: 30 seconds")
            driver.set_page_load_timeout(30)
            driver.set_script_timeout(30)
            
            logger.info(f"Navigating to URL: {url}")
            driver.get(url)
            logger.debug("Page loaded successfully")
            
            # --- Step 1: Fill in the search form ---
            logger.debug(f"Selecting FIR year: {year}")
            year_select = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_ddFIRYear"))
            )
            Select(year_select).select_by_value(year)
            logger.debug("Year selected successfully")
            
            logger.debug(f"Selecting district: {district}")
            district_select = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_ddlDistrict"))
            )
            Select(district_select).select_by_visible_text(district)
            logger.debug("District selected successfully")
            
            logger.debug(f"Waiting for police station dropdown to populate")
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//select[@id='ContentPlaceHolder1_ddlPoliceStation']/option[not(contains(text(),'Select'))]"))
            )
            logger.debug(f"Selecting police station: {police_station}")
            police_station_select = driver.find_element(By.ID, "ContentPlaceHolder1_ddlPoliceStation")
            Select(police_station_select).select_by_visible_text(police_station)
            logger.debug("Police station selected successfully")
            
            # Enter the FIR number
            fir_number_input = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_txtRegistrationNumber"))
            )
            fir_number_input.send_keys(fir_number)
            
            # Click the search button
            search_button = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.ID, "ContentPlaceHolder1_btnStatusSearch"))
            )
            search_button.click()
            
            # --- Step 2: Click the "View FIR" link ---
            view_fir_link = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.LINK_TEXT, 'View FIR'))
            )
            
            # Store the main window handle before clicking
            logger.debug("Storing initial window handles")
            initial_handles = driver.window_handles
            logger.debug(f"Initial window handles count: {len(initial_handles)}")
            view_fir_link.click()
            
            # Check if new window/tab opened - use WebDriverWait for dynamic wait
            WebDriverWait(driver, 30).until(
                lambda d: len(d.window_handles) > len(initial_handles)
            )
            
            # Switch to the newly opened window/tab
            new_handles = driver.window_handles
            new_window = [handle for handle in new_handles if handle not in initial_handles][0]
            driver.switch_to.window(new_window)
            
            # Wait until the current URL changes from the original with longer timeout
            WebDriverWait(driver, 30).until(
                lambda d: d.current_url != url and "javascript:" not in d.current_url
            )
            real_pdf_url = driver.current_url
            logger.info(f"Real PDF URL: {real_pdf_url}")

            # --- Step 3: Multiple approaches to find the export button ---
            export_button = None
            export_button_strategies = [
                # By title attribute containing 'export'
                ("By title", By.XPATH, "//*[contains(translate(@title, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'Export')]"),
                # By class that might contain export icons
                ("By class", By.XPATH, "//div[contains(@class, 'Export') or contains(@class, 'download')]"),
                # By image attributes
                ("By image", By.XPATH, "//img[contains(@src, 'Export') or contains(@src, 'download') or contains(@src, 'save')]"),
                # By button text
                ("By text", By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'Export') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'save')]")
            ]
            
            for strategy_name, by_method, selector in export_button_strategies:
                try:
                    logger.info(f"Trying to find export button {strategy_name}: {selector}")
                    export_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((by_method, selector))
                    )
                    if export_button:
                        logger.info(f"Found export button using {strategy_name}")
                        break
                except Exception as e:
                    logger.warning(f"Strategy {strategy_name} failed: {str(e)}")
            
            # If all strategies failed, try a more aggressive approach - look for any button/link
            if not export_button:
                try:
                    logger.info("Trying fallback strategy: look for elements at top right")
                    # Try to find elements in the top toolbar area
                    toolbar_elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'toolbar') or contains(@class, 'header')]//button | //div[contains(@class, 'toolbar') or contains(@class, 'header')]//a")
                    
                    if toolbar_elements:
                        # Try elements from right to left (export is usually on right)
                        for element in reversed(toolbar_elements):
                            try:
                                if element.is_displayed() and element.is_enabled():
                                    export_button = element
                                    logger.info("Found potential export button in toolbar")
                                    break
                            except:
                                continue
                except Exception as e:
                    logger.warning(f"Fallback strategy failed: {str(e)}")
            
            if not export_button:
                raise Exception("Could not find export button with any strategy")
                
            # Click the export button
            driver.execute_script("arguments[0].scrollIntoView(true);", export_button)
            driver.execute_script("arguments[0].click();", export_button)
            logger.info("Clicked export button")
            
            # --- Step 4: Multiple strategies to find PDF option ---
            # Use a condition to wait for dropdown/menu to appear rather than sleep
            try:
                # Wait for any changes in DOM that might indicate menu has appeared
                WebDriverWait(driver, 10).until(
                    lambda d: len(d.find_elements(By.XPATH, "//a[contains(text(),'PDF')] | //li[contains(text(),'PDF')]")) > 0 or 
                    len(d.find_elements(By.XPATH, "//button[contains(text(),'PDF')] | //div[contains(text(),'PDF')]")) > 0
                )
            except:
                logger.info("No explicit PDF menu detected, continuing with strategies")
            
            pdf_option = None
            pdf_option_strategies = [
                # By text content
                ("By text", By.XPATH, "//a[contains(text(),'PDF')] | //button[contains(text(),'PDF')] | //div[contains(text(),'PDF')]"),
                # By menu items
                ("By menu item", By.XPATH, "//li[contains(text(),'PDF')] | //span[contains(text(),'PDF')]"),
                # By image or icon with PDF attributes
                ("By icon", By.XPATH, "//img[contains(@src, 'pdf')] | //i[contains(@class, 'pdf')]")
            ]
            
            for strategy_name, by_method, selector in pdf_option_strategies:
                try:
                    logger.info(f"Trying to find PDF option {strategy_name}: {selector}")
                    pdf_option = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((by_method, selector))
                    )
                    if pdf_option:
                        logger.info(f"Found PDF option using {strategy_name}")
                        break
                except Exception as e:
                    logger.warning(f"PDF strategy {strategy_name} failed: {str(e)}")
            
            if not pdf_option:
                # If we can't find PDF option, check if we're already on a PDF page
                if "pdf" in driver.current_url.lower():
                    logger.info("Already on PDF page, proceeding with download")
                else:
                    raise Exception("Could not find PDF option with any strategy")
            else:
                # Click the PDF option
                driver.execute_script("arguments[0].scrollIntoView(true);", pdf_option)
                driver.execute_script("arguments[0].click();", pdf_option)
                logger.info("Clicked PDF option")

            # If clicking the PDF option opens a new window/tab, check and switch
            # Use WebDriverWait to dynamically wait for new tab
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: len(d.window_handles) > len(new_handles)
                )
                
                current_handles = driver.window_handles
                new_window2 = [handle for handle in current_handles if handle not in new_handles][0]
                driver.switch_to.window(new_window2)
            except:
                logger.info("No new tab opened after clicking PDF option")

            # Wait until the URL changes from the previous one or timeout after 30 seconds
            try:
                WebDriverWait(driver, 30).until(lambda d: d.current_url != real_pdf_url)
                final_pdf_url = driver.current_url
                logger.info(f"Final PDF URL: {final_pdf_url}")
            except:
                logger.warning("URL did not change, but continuing with download check")
            
            # Wait for the file to be downloaded with increased timeout
            max_wait_time = 60
            wait_interval = 0.5
            waited_time = 0
            
            logger.info("Starting download monitoring")
            download_successful = WebDriverWait(driver, max_wait_time).until(
                lambda d: os.path.exists(expected_file_path) and os.path.getsize(expected_file_path) > 0
            )
            logger.debug(f"Download successful: {download_successful}")
            
            if download_successful:
                logger.info("Verifying downloaded file integrity")
                try:
                    with open(expected_file_path, 'rb') as file:
                        # Check if file has actual content
                        content = file.read(1024)
                        if content:  # If we have some content, file is likely downloaded
                            logger.info(f"File verification successful: {expected_file_path}")
                            return expected_file_path
                except PermissionError:
                    # If still being written, wait a bit more then return
                    WebDriverWait(driver, 10).until(
                        lambda d: os.access(expected_file_path, os.R_OK)
                    )
                    return expected_file_path
                except Exception as e:
                    logger.error(f"File verification failed: {str(e)}")
            
            logger.warning(f"Download timeout after {max_wait_time} seconds")
            
            # If file exists, return it even if we timed out (it might be partially downloaded)
            if os.path.exists(expected_file_path):
                return expected_file_path
                
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed with error: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            if attempt < max_retries - 1:
                logger.info(f"Waiting before retry {attempt + 2}")
                # Use a WebDriverWait equivalent instead of sleep
                # (In this case we just need to wait between retries, so we'll use a dummy condition)
                try:
                    if driver:
                        WebDriverWait(driver, 5).until(lambda d: False)
                except:
                    pass  # Expected timeout after 5 seconds
            else:
                logger.error(f"All {max_retries} attempts failed.")
                # Return expected path even if download failed - allows caller to check if file exists
                return expected_file_path
        finally:
            if driver:
                logger.debug("Cleaning up WebDriver")
                try:
                    driver.quit()
                    logger.debug("WebDriver closed successfully")
                except Exception as e:
                    logger.warning(f"Error closing WebDriver: {str(e)}")
    
    logger.warning(f"All {max_retries} attempts completed. Returning expected file path: {expected_file_path}")
    return expected_file_path  # Return expected path even if all attempts failed
