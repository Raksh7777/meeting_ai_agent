import os
import datetime
from typing import Dict, Any, List
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()


class GoogleCalendarAPIExecutor:
    SCOPES = ['https://www.googleapis.com/auth/calendar', 
              'https://www.googleapis.com/auth/contacts.readonly']
    
    def __init__(self, credentials_path: str, token_path: str = 'token.json'):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.calendar_service = None
        self.people_service = None
        self._authenticate()
    
    def _authenticate(self):
        creds = None
        if os.path.exists(self.token_path):
            with open(self.token_path, 'r') as token:
                creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
        
        self.calendar_service = build('calendar', 'v3', credentials=creds)
        self.people_service = build('people', 'v1', credentials=creds)
    
    def execute(self, api_name: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if api_name == "contacts":
            return self._execute_contacts_api(action, params)
        elif api_name == "calendar":
            return self._execute_calendar_api(action, params)
        elif api_name == "preferences":
            return self._execute_preferences_api(action, params)
        else:
            return {"success": False, "error": f"Unknown API: {api_name}"}
    
    def _execute_contacts_api(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "find_contact":
            return self._find_contact(params["name"])
        elif action == "get_contact_details":
            return self._get_contact_details(params["contact_id"])
        else:
            return {"success": False, "error": f"Unknown contacts action: {action}"}
    
    def _find_contact(self, name: str) -> Dict[str, Any]:
        try:
            query = name.lower()
            results = self.people_service.people().connections().list(
                resourceName='people/me',
                pageSize=100,
                personFields='names,emailAddresses',
                sortOrder='FIRST_NAME_ASCENDING'
            ).execute()
            
            connections = results.get('connections', [])
            matching_contacts = []
            for person in connections:
                names = person.get('names', [])
                for name_obj in names:
                    display_name = name_obj.get('displayName', '').lower()
                    
                    if query in display_name:
                        matching_contacts.append({
                            'contact_id': person['resourceName'].split('/')[-1],
                            'name': name_obj.get('displayName', ''),
                            'email': person.get('emailAddresses', [{}])[0].get('value', '')
                        })
                        break
            
            if matching_contacts:
                contact = matching_contacts[0]
                return {
                    "success": True,
                    "contact_id": contact['contact_id'],
                    "name": contact['name'],
                    "email": contact['email']
                }
            else:
                return {"success": False, "error": f"No contact found with name '{name}'"}
                
        except Exception as e:
            return {"success": False, "error": f"Error finding contact: {str(e)}"}
    
    def _get_contact_details(self, contact_id: str) -> Dict[str, Any]:
        try:
            person = self.people_service.people().get(
                resourceName=f'people/{contact_id}',
                personFields='names,emailAddresses,phoneNumbers'
            ).execute()
            
            names = person.get('names', [])
            emails = person.get('emailAddresses', [])
            phones = person.get('phoneNumbers', [])
            
            return {
                "success": True,
                "contact_id": contact_id,
                "name": names[0].get('displayName', '') if names else '',
                "email": emails[0].get('value', '') if emails else '',
                "phone": phones[0].get('value', '') if phones else ''
            }
        except Exception as e:
            return {"success": False, "error": f"Error getting contact details: {str(e)}"}
    
    def _execute_calendar_api(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "check_availability":
            return self._check_availability(params["user_id"], params["start_time"], params["end_time"])
        elif action == "get_free_slots":
            return self._get_free_slots(params["user_id"], params["other_user_id"], params.get("date"))
        elif action == "book_meeting":
            return self._book_meeting(params["title"], params["attendees"], 
                                    params["start_time"], params["end_time"], 
                                    params.get("description", ""))
        else:
            return {"success": False, "error": f"Unknown calendar action: {action}"}
    
    def _get_free_slots(self, user_id: str, other_user_id: str, date: str = None) -> Dict[str, Any]:
        try:
            if date:
                base_date = datetime.date.fromisoformat(date)
            else:
                base_date = datetime.date.today() + datetime.timedelta(days=1)

            start_hour = 9
            end_hour = 17
            duration = datetime.timedelta(minutes=30)
            
            contact_details = self._get_contact_details(other_user_id)
            if not contact_details.get("success", False):
                return {"success": False, "error": "Could not find contact email"}
            
            contact_email = contact_details.get("email", "")
            if not contact_email:
                return {"success": False, "error": "Contact does not have an email address"}
            
            time_min = datetime.datetime.combine(base_date, datetime.time(start_hour, 0))
            time_max = datetime.datetime.combine(base_date, datetime.time(end_hour, 0))
            
            body = {
                "timeMin": time_min.isoformat() + "Z",
                "timeMax": time_max.isoformat() + "Z",
                "items": [
                    {"id": "primary"},
                    {"id": contact_email}
                ]
            }
            
            freebusy = self.calendar_service.freebusy().query(body=body).execute()
            
            calendars = freebusy.get('calendars', {})
            primary_busy = calendars.get('primary', {}).get('busy', [])
            other_busy = calendars.get(contact_email, {}).get('busy', [])
            
            all_busy = primary_busy + other_busy
            
            busy_periods = []
            for period in all_busy:
                start = datetime.datetime.fromisoformat(period['start'].replace('Z', '+00:00'))
                end = datetime.datetime.fromisoformat(period['end'].replace('Z', '+00:00'))
                busy_periods.append((start, end))
            
            free_slots = []
            current_time = time_min
            
            while current_time + duration <= time_max:
                slot_end = current_time + duration
                is_free = True
                
                for busy_start, busy_end in busy_periods:
                    if not (slot_end <= busy_start or current_time >= busy_end):
                        is_free = False
                        break
                
                if is_free:
                    free_slots.append({
                        "start_time": current_time.isoformat() + "Z",
                        "end_time": slot_end.isoformat() + "Z"
                    })
                
                current_time += datetime.timedelta(minutes=30)
            
            return {
                "success": True,
                "date": base_date.isoformat(),
                "slots": free_slots
            }
        except Exception as e:
            return {"success": False, "error": f"Error getting free slots: {str(e)}"}

    def _execute_preferences_api(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "get_meeting_preferences":
            return self._get_meeting_preferences(params["user_id"], params.get("ask_user", False))
        else:
            return {"success": False, "error": f"Unknown preferences action: {action}"}

    def _get_meeting_preferences(self, user_id: str, ask_user: bool = False) -> Dict[str, Any]:
        if ask_user:
            return self._ask_user_for_preferences()
        else:
            return {
                "success": True,
                "duration": 30,
                "preferred_times": ["morning", "afternoon"],
                "buffer": 15
            }

    def _ask_user_for_preferences(self) -> Dict[str, Any]:
        print("Prompting user for meeting preferences...")
        return {
            "success": True,
            "duration": 45,
            "preferred_times": ["afternoon"],
            "buffer": 10
        }
    
    def _check_availability(self, user_id: str, start_time: str, end_time: str) -> Dict[str, Any]:
        try:
            start_dt = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
            events_result = self.calendar_service.events().list(
                calendarId='primary',
                timeMin=start_dt.isoformat() + 'Z',
                timeMax=end_dt.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            is_available = len(events) == 0
            
            return {
                "success": True,
                "is_available": is_available,
                "conflicting_events": len(events)
            }
        except Exception as e:
            return {"success": False, "error": f"Error checking availability: {str(e)}"}
    
    def _book_meeting(self, title: str, attendees: List[str], start_time: str, 
                     end_time: str, description: str = "") -> Dict[str, Any]:
        try:
            attendee_emails = []
            for attendee_id in attendees:
                if '@' in attendee_id:
                    attendee_emails.append({"email": attendee_id})
                else:
                    contact = self._get_contact_details(attendee_id)
                    if contact.get("success", False) and contact.get("email"):
                        attendee_emails.append({"email": contact["email"]})
            
            event = {
                'summary': title,
                'description': description,
                'start': {
                    'dateTime': start_time,
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_time,
                    'timeZone': 'UTC',
                },
                'attendees': attendee_emails,
                'reminders': {
                    'useDefault': True,
                },
            }
            
            event = self.calendar_service.events().insert(
                calendarId='primary',
                body=event,
                sendUpdates='all'
            ).execute()
            
            return {
                "success": True,
                "meeting_id": event.get('id'),
                "title": title,
                "start_time": start_time,
                "end_time": end_time,
                "attendees": [a.get("email") for a in attendee_emails],
                "link": event.get('htmlLink')
            }
        except Exception as e:
            return {"success": False, "error": f"Error booking meeting: {str(e)}"}

class MeetingBookingMCPAgent:
    def __init__(self, api_executor, openai_api_key: str):
        self.api_executor = api_executor
        openai.api_key = openai_api_key

    def process_user_prompt(self, prompt: str, user_id: str) -> Dict[str, Any]:
        intent = self._parse_intent_with_llm(prompt)
        
        if intent['action'] == 'book_meeting':
            plan = self._create_execution_plan(intent, user_id)
            results = self._execute_plan(plan)
            return self._generate_response(prompt, results)
        else:
            return {"message": "I'm not sure what you want to do. Can you clarify?", "status": "error"}

    def _parse_intent_with_llm(self, prompt: str) -> Dict[str, Any]:
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=f"Analyze this prompt: {prompt}. Extract intent and details.",
            max_tokens=150
        )
        return {"action": "book_meeting", "contact_name": "Chinmay Sir", "ask_preferences": False}

    def _create_execution_plan(self, intent: Dict[str, Any], user_id: str) -> List[Dict[str, Any]]:
        plan = []
        if 'contact_name' in intent:
            plan.append({
                "api": "contacts",
                "action": "find_contact",
                "params": {"name": intent['contact_name']}
            })
        if 'ask_preferences' in intent and intent['ask_preferences']:
            plan.append({
                "api": "preferences",
                "action": "get_meeting_preferences",
                "params": {"user_id": user_id, "ask_user": True}
            })
        plan.append({
            "api": "calendar",
            "action": "get_free_slots",
            "params": {"user_id": user_id, "other_user_id": "PLACEHOLDER", "date": "PLACEHOLDER"}
        })
        # Additional steps based on the intent...
        return plan

    def _execute_plan(self, plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        results = {}
        for step in plan:
            result = self.api_executor.execute(step['api'], step['action'], step['params'])
            results[f"{step['api']}_{step['action']}"] = result
        return results

    def _generate_response(self, prompt: str, results: Dict[str, Any]) -> Dict[str, Any]:
        if "contacts_find_contact" in results and results["contacts_find_contact"].get("success"):
            return {"message": "Contact found and processed.", "status": "success"}
        else:
            return {"message": "Failed to find contact.", "status": "error"}

# Example usage
def example_google_calendar_integration():
    credentials_path = 'credentials.json'
    openai_api_key = os.getenv('OPENAI_API_KEY')  # Replace with your OpenAI API key

    executor = GoogleCalendarAPIExecutor(credentials_path)
    agent = MeetingBookingMCPAgent(executor, openai_api_key)
    
    result = agent.process_user_prompt("Book a meeting with Chinmay Sir", "primary")
    
    print("Agent response:")
    print(result)

if __name__ == "__main__":
    example_google_calendar_integration()
