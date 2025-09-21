from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from ics import Calendar, Event
import time
from datetime import datetime
import os
import json

# The file to store IDs and due dates of assignments that have already been processed
PROCESSED_FILE = 'processed_assignments.json'

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
            items = soup.find_all('div', class_='schedule-show-control')
            for item in items:
                if '[과제]' in item.text:
                    details_div = item.find_next_sibling('div', class_='changeDetile')
                    if details_div and details_div.find('a'):
                        onclick_attr = details_div.find('a').get('onclick', '')
                        if 'RT_SEQ=' in onclick_attr:
                            assignment_id = onclick_attr.split('RT_SEQ=')[1].split("'")[0]
                            due_date_tag = details_div.find('div', string=lambda t: t and '마감일' in t)
                            course_name_tag = details_div.find('div', class_='schedule_view_title')
                            assignment_name_tag = item.find('span')

                            if not all([due_date_tag, course_name_tag, assignment_name_tag]): continue

                            due_date_str = due_date_tag.text.replace('마감일 :','').strip()
                            course_name = course_name_tag.text.strip().split('(')[0].strip()
                            assignment_name = assignment_name_tag.text.strip()
                            relative_link = onclick_attr.split(',')[1].strip().strip("'").replace('report_insert_form.acl', 'report_view_form.acl')
                            full_link = f"{LMS_URL}{relative_link}"

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

    # --- Filter for new or updated assignments ---
    final_assignments = []
    for assign in all_assignments:
        if assign['id'] not in processed_data or processed_data[assign['id']] != assign['due_date_str']:
            final_assignments.append(assign)

    # --- Create iCalendar (.ics) file ---
    if final_assignments:
        print(f"\nFound {len(final_assignments)} new or updated assignments.")
        print(f"Creating calendar file: lms_assignments.ics")
        c = Calendar()
        for assignment in final_assignments:
            due_date = parse_due_date(assignment['due_date_str'])
            if not due_date: continue
            
            e = Event()
            e.uid = f"{assignment['id']}@lms.mju.ac.kr"
            e.name = f"[{assignment['course']}] {assignment['title']}"
            e.begin = due_date
            e.make_all_day()
            e.description = assignment['link'] # Set description to URL only
            e.created = datetime.now()
            c.events.add(e)
            processed_data[assignment['id']] = assignment['due_date_str']

        with open('lms_assignments.ics', 'w', encoding='utf-8') as f:
            f.writelines(c)
        print("\nSuccessfully created lms_assignments.ics file!")
    else:
        print("\nNo new or updated assignments found.")

    # --- Update the processed assignments file ---
    with open(PROCESSED_FILE, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, indent=2, ensure_ascii=False)
    print(f"Updated {PROCESSED_FILE} with latest assignment data.")

    # --- Close browser ---
    driver.quit()
    print("\nAll tasks completed.")

if __name__ == "__main__":
    main()
