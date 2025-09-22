from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import os
import json
import pickle
import re # Import re for regular expressions
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# The file to store IDs and due dates of assignments that have already been processed
PROCESSED_FILE = 'processed_assignments.json'
# Scopes for Google Calendar API
SCOPES = ['https://www.googleapis.com/auth/calendar']
# Token file for Google API
TOKEN_FILE = 'token.pickle'

def get_calendar_service():
    """Authenticates with Google and returns the Calendar service object."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    
    service = build('calendar', 'v3', credentials=creds)
    return service

def parse_due_date(date_str):
    """Parses the specific date format from the LMS."""
    if not date_str: return None
    try:
        if '오후' in date_str:
            date_str_formatted = date_str.replace('오후', 'PM').strip()
            dt_obj = datetime.strptime(date_str_formatted, '%Y.%m.%d %p %I:%M')
        elif '오전' in date_str:
            date_str_formatted = date_str.replace('오전', 'AM').strip()
            dt_obj = datetime.strptime(date_str_formatted, '%Y.%m.%d %p %I:%M')
        else:
            dt_obj = datetime.strptime(date_str, '%Y.%m.%d')
        return dt_obj
    except ValueError as e:
        print(f"Could not parse date: '{date_str}'. Error: {e}")
        return None

def main():
    # --- Load already processed assignment data ---
    processed_data = {}
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r', encoding='utf-8') as f:
            try: processed_data = json.load(f)
            except json.JSONDecodeError: print(f"Warning: Could not decode {PROCESSED_FILE}.")
    print(f"Loaded {len(processed_data)} previously processed assignment records.")

    # --- Load Configuration & WebDriver Setup ---
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        LMS_URL = config['LMS_URL']
        USERNAME = config['USERNAME']
        PASSWORD = config['PASSWORD']
    except FileNotFoundError:
        print("Error: config.json not found. Please create it with your credentials.")
        return
    except KeyError:
        print("Error: config.json is missing required keys (LMS_URL, USERNAME, PASSWORD).")
        return

    driver = webdriver.Chrome()
    wait = WebDriverWait(driver, 15)

    # --- Login Process ---
    try:
        driver.get(LMS_URL)
        print(f"Navigated to {LMS_URL}")
        login_page_button = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href='/ilos/main/member/login_form.acl']")))
        driver.execute_script("arguments[0].click();", login_page_button)
        print("Clicked the initial login button.")
        wait.until(EC.element_to_be_clickable((By.ID, "sso_btn"))).click()
        print("Clicked the '통합로그인 서비스' button.")
        wait.until(EC.element_to_be_clickable((By.ID, "id"))).send_keys(USERNAME)
        driver.find_element(By.ID, "passwrd").send_keys(PASSWORD)
        driver.find_element(By.ID, "loginButton").click()
        print("Submitted credentials.")
        wait.until(EC.presence_of_element_located((By.ID, "user")))
        print("Login successful!")
    except Exception as e:
        print(f"An error occurred during login: {e}")
        driver.quit()
        return

    # --- Navigate to Schedule List ---
    print("\nChecking for assignment list...")
    try:
        wait.until(EC.presence_of_element_located((By.ID, "shedule_list_form")))
        print("Assignment list is already displayed.")
    except:
        print("Finding and clicking the 'Schedule List View' button...")
        try:
            wait.until(EC.element_to_be_clickable((By.ID, "show_schedule_list"))).click()
            wait.until(EC.presence_of_element_located((By.ID, "shedule_list_form")))
            print("Clicked '목록보기' button.")
        except Exception as e:
            print(f"Could not find or click the schedule list view button: {e}")
            driver.quit()
            return

    # --- Scrape assignment info from all relevant months ---
    all_assignments = []
    unique_ids = set()
    for i in range(4): # Crawl current month + next 3 months
        print(f"\n--- Parsing Month {i+1}/4 ---")
        try:
            list_container = wait.until(EC.presence_of_element_located((By.ID, "shedule_list_form")))
            soup = BeautifulSoup(list_container.get_attribute('outerHTML'), 'html.parser')
            items = soup.select('div.schedule-show-control')
            for item in items:
                if '[과제]' in item.text:
                    details_div = item.find_next_sibling('div', class_='changeDetile')
                    if details_div and details_div.select_one('a'):
                        onclick_attr = details_div.select_one('a').get('onclick', '')
                        
                        # Use regex to reliably extract the assignment ID
                        match = re.search(r"RT_SEQ=(\d+)", onclick_attr)
                        if not match:
                            continue # Skip if no ID is found
                        
                        assignment_id = match.group(1)

                        due_date_tag = details_div.find('div', string=lambda t: t and '마감일' in t)
                        course_name_tag = details_div.select_one('div.schedule_view_title')
                        assignment_name_tag = item.select_one('span')

                        if not all([due_date_tag, course_name_tag, assignment_name_tag]): 
                            continue

                        due_date_str = due_date_tag.text.replace('마감일 :','').strip()
                        course_name = course_name_tag.text.strip().split('(')[0].strip()
                        assignment_name = assignment_name_tag.text.strip()
                        full_link = LMS_URL

                        if assignment_id not in unique_ids:
                            unique_ids.add(assignment_id)
                            all_assignments.append({
                                "id": assignment_id, "course": course_name, "title": assignment_name,
                                "due_date_str": due_date_str, "link": full_link
                            })
        except Exception as e:
            print(f"Error parsing assignment list: {e}")
        
        try:
            current_month_text = driver.find_element(By.ID, "Month").text
            driver.find_element(By.CSS_SELECTOR, "input[onclick*='getMainScheduleList(\'at\')']").click()
            wait.until(lambda d: d.find_element(By.ID, "Month").text != current_month_text, "Timeout waiting for month to change")
            print("Navigated to the next month.")
        except Exception:
            print("Could not navigate to the next month. Assuming end of schedule.")
            break

    # --- Close browser ---
    driver.quit()

    # --- Filter for new or updated assignments ---
    new_or_updated_assignments = []
    for assign in all_assignments:
        if assign['id'] not in processed_data or processed_data[assign['id']] != assign['due_date_str']:
            new_or_updated_assignments.append(assign)

    # --- Sync with Google Calendar ---
    if new_or_updated_assignments:
        print(f"\nFound {len(new_or_updated_assignments)} new or updated assignments. Syncing with Google Calendar...")
        service = get_calendar_service()
        
        for assignment in new_or_updated_assignments:
            due_date = parse_due_date(assignment['due_date_str'])
            if not due_date: continue

            event_uid = f"{assignment['id']}@lms.mju.ac.kr"
            event_summary = f"[{assignment['course']}] {assignment['title']}"
            
            # For all-day events, the end date should be the day after the start date.
            event_start = {'date': due_date.strftime('%Y-%m-%d')}
            event_end = {'date': (due_date + timedelta(days=1)).strftime('%Y-%m-%d')}

            event_body = {
                'summary': event_summary,
                'description': f"LMS 바로가기: {assignment['link']}",
                'start': event_start,
                'end': event_end,
                'iCalUID': event_uid, # Use assignment ID for unique identification
            }

            try:
                # Check if event already exists
                events_result = service.events().list(calendarId='primary', iCalUID=event_uid).execute()
                existing_event = events_result.get('items', [])

                if existing_event:
                    # Update existing event
                    updated_event = service.events().update(calendarId='primary', eventId=existing_event[0]['id'], body=event_body).execute()
                    print(f"Updated event: {updated_event.get('summary')}")
                else:
                    # Create new event
                    created_event = service.events().insert(calendarId='primary', body=event_body).execute()
                    print(f"Created event: {created_event.get('summary')}")
                
                # Update processed data upon successful API call
                processed_data[assignment['id']] = assignment['due_date_str']

            except Exception as e:
                print(f"An error occurred while syncing event '{event_summary}': {e}")

    else:
        print("\nNo new or updated assignments found.")

    # --- Update the processed assignments file ---
    with open(PROCESSED_FILE, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, indent=2, ensure_ascii=False)
    print(f"Updated {PROCESSED_FILE} with latest assignment data.")
    print("\nAll tasks completed.")

if __name__ == "__main__":
    main()
