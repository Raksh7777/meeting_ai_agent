import os
import datetime
from typing import Dict, Any, List
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle

class GoogleCalendarAPIExecutor:
    """API executor implementation for Google Calendar integration"""
    
    # If modifying these scopes, delete the token.json file
    SCOPES = ['https://www.googleapis.com/auth/calendar', 
              'https://www.googleapis.com/auth/contacts.readonly']
    
    def __init__(self, credentials_path: str, token_path: str = 'token.json'):
        """
        Initialize the Google Calendar API executor
        
        Args:
            credentials_path: Path to the credentials.json file from Google Cloud Console
            token_path: Path where the OAuth token will be stored
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.calendar_service = None
        self.people_service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google APIs and build service objects"""
        creds = None
        
        # Load token from file if it exists
        if os.path.exists(self.token_path):
            with open(self.token_path, 'r') as token:
                creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)
        
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
        
        # Build the services
        self.calendar_service = build('calendar', 'v3', credentials=creds)
        self.people_service = build('people', 'v1', credentials=creds)
    
    def execute(self, api_name: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an API call
        
        Args:
            api_name: The API to call (contacts, calendar, preferences)
            action: The specific action to perform
            params: Parameters for the action
            
        Returns:
            Result of the API call
        """
        if api_name == "contacts":
            return self._execute_contacts_api(action, params)
        elif api_name == "calendar":
            return self._execute_calendar_api(action, params)
        elif api_name == "preferences":
            return self._execute_preferences_api(action, params)
        else:
            return {"success": False, "error": f"Unknown API: {api_name}"}
    
    def _execute_contacts_api(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute contacts-related API calls"""
        if action == "find_contact":
            return self._find_contact(params["name"])
        elif action == "get_contact_details":
            return self._get_contact_details(params["contact_id"])
        else:
            return {"success": False, "error": f"Unknown contacts action: {action}"}
    
    def _execute_calendar_api(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute calendar-related API calls"""
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
    
    def _execute_preferences_api(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute preferences-related API calls"""
        if action == "get_meeting_preferences":
            return self._get_meeting_preferences(params["user_id"])
        else:
            return {"success": False, "error": f"Unknown preferences action: {action}"}
    

    
    def _get_contact_details(self, contact_id: str) -> Dict[str, Any]:
        """Get contact details by ID using Google People API"""
        try:
            person = self.people_service.people().get(
                resourceName=f'people/{contact_id}',
                personFields='names,emailAddresses,phoneNumbers'
            ).execute()
            
            # Extract relevant information
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
    
    def _check_availability(self, user_id: str, start_time: str, end_time: str) -> Dict[str, Any]:
        """Check if a user is available during a specific time slot"""
        try:
            # Convert string times to datetime
            start_dt = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
            # Get events in the specified time range
            events_result = self.calendar_service.events().list(
                calendarId='primary',
                timeMin=start_dt.isoformat() + 'Z',
                timeMax=end_dt.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # The user is available if there are no events
            is_available = len(events) == 0
            
            return {
                "success": True,
                "is_available": is_available,
                "conflicting_events": len(events)
            }
        except Exception as e:
            return {"success": False, "error": f"Error checking availability: {str(e)}"}
    
    def _get_free_slots(self, user_id: str, other_user_id: str, date: str = None) -> Dict[str, Any]:
        """Get free time slots for a meeting between two users"""
        try:
            # Set time boundaries
            if date:
                # Use the specified date
                try:
                    base_date = datetime.date.fromisoformat(date)
                except:
                    # Default to tomorrow if date format is invalid
                    base_date = datetime.date.today() + datetime.timedelta(days=1)
            else:
                # Default to tomorrow
                base_date = datetime.date.today() + datetime.timedelta(days=1)
            
            # Set working hours (9 AM to 5 PM)
            start_hour = 9
            end_hour = 17
            
            # Duration for the meeting (default 30 minutes)
            duration = datetime.timedelta(minutes=30)
            
            # Get contact details to find email
            contact_details = self._get_contact_details(other_user_id)
            if not contact_details.get("success", False):
                return {"success": False, "error": "Could not find contact email"}
            
            contact_email = contact_details.get("email", "")
            if not contact_email:
                return {"success": False, "error": "Contact does not have an email address"}
            
            # Set up the free/busy query
            time_min = datetime.datetime.combine(base_date, datetime.time(start_hour, 0))
            time_max = datetime.datetime.combine(base_date, datetime.time(end_hour, 0))
            
            body = {
                "timeMin": time_min.isoformat() + "Z",
                "timeMax": time_max.isoformat() + "Z",
                "items": [
                    {"id": "primary"},  # Current user's calendar
                    {"id": contact_email}  # Other user's calendar
                ]
            }
            
            # Make the freebusy query
            freebusy = self.calendar_service.freebusy().query(body=body).execute()
            
            # Process the response
            calendars = freebusy.get('calendars', {})
            primary_busy = calendars.get('primary', {}).get('busy', [])
            other_busy = calendars.get(contact_email, {}).get('busy', [])
            
            # Combine busy periods
            all_busy = primary_busy + other_busy
            
            # Convert busy periods to datetime objects
            busy_periods = []
            for period in all_busy:
                start = datetime.datetime.fromisoformat(period['start'].replace('Z', '+00:00'))
                end = datetime.datetime.fromisoformat(period['end'].replace('Z', '+00:00'))
                busy_periods.append((start, end))
            
            # Find free slots
            free_slots = []
            current_time = time_min
            
            while current_time + duration <= time_max:
                slot_end = current_time + duration
                is_free = True
                
                # Check if this slot overlaps with any busy period
                for busy_start, busy_end in busy_periods:
                    if not (slot_end <= busy_start or current_time >= busy_end):
                        is_free = False
                        break
                
                if is_free:
                    free_slots.append({
                        "start_time": current_time.isoformat() + "Z",
                        "end_time": slot_end.isoformat() + "Z"
                    })
                
                # Move to next slot (30-minute increments)
                current_time += datetime.timedelta(minutes=30)
            
            return {
                "success": True,
                "date": base_date.isoformat(),
                "slots": free_slots
            }
        except Exception as e:
            return {"success": False, "error": f"Error getting free slots: {str(e)}"}
    
    def _book_meeting(self, title: str, attendees: List[str], start_time: str, 
                     end_time: str, description: str = "") -> Dict[str, Any]:
        """Book a meeting on Google Calendar"""
        try:
            # Convert attendee IDs to email addresses if needed
            attendee_emails = []
            for attendee_id in attendees:
                if '@' in attendee_id:  # Already an email
                    attendee_emails.append({"email": attendee_id})
                else:  # Contact ID, need to get email
                    contact = self._get_contact_details(attendee_id)
                    if contact.get("success", False) and contact.get("email"):
                        attendee_emails.append({"email": contact["email"]})
            
            # Create the event
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
                sendUpdates='all'  # Send emails to attendees
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
    
    def _get_meeting_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get user preferences for meetings"""
        # In a real implementation, you would fetch these from a database
        # Here we'll return hardcoded preferences
        return {
            "success": True,
            "duration": 30,  # minutes
            "preferred_times": ["morning", "afternoon"],
            "buffer": 15  # minutes before and after meetings
        }

# Example usage
def example_google_calendar_integration():
    # Path to your OAuth credentials file from Google Cloud Console
    credentials_path = 'credentials.json'
    
    # Create the executor
    executor = GoogleCalendarAPIExecutor(credentials_path)
    
    # Create the MCP agent with the Google Calendar executor
    from meeting_booking_agent import MeetingBookingMCPAgent
    agent = MeetingBookingMCPAgent(executor)
    
    # Process a user prompt
    result = agent.process_user_prompt("Book a meeting with John", "primary")
    
    print("Agent response:")
    print(result)

if __name__ == "__main__":
    example_google_calendar_integration()