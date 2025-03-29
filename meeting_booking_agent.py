import json
from typing import List, Dict, Any
from datetime import datetime
from google_calendar_integration_openai import  GoogleCalendarAPIExecutor
import openai
from dotenv import load_dotenv
import os

from typing import Dict, Any
load_dotenv()


class MeetingBookingMCPAgent:
    def __init__(self, api_executor, openai_api_key: str):
        self.api_executor = api_executor
        openai.api_key = openai_api_key
        self.pending_action = None

    def process_user_prompt(self, prompt: str, user_id: str) -> Dict[str, Any]:
      
        intent = self._parse_intent_with_llm(prompt)
        
        if intent['action'] == 'book_meeting':
            plan = self._create_execution_plan(intent, user_id)
            results = self._execute_plan(plan)
            return self._generate_response(prompt, results)
        else:
            return {"message": "I'm not sure what you want to do. Can you clarify?", "status": "error"}

    def _parse_intent_with_llm(self, prompt: str) -> Dict[str, Any]:
        # Using the new ChatCompletion API call
        client= openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"Analyze this prompt: {prompt}. Extract intent and details."}
            ]
        )
        message_content = response.choices[0].message.content
        # Here, you need to parse `message_content` into a Python dictionary
        # This is an example assuming the response contains JSON-like structure
        return {"action": "book_meeting", "contact_name": "Chinmay Sir", "ask_preferences": False}

    # Other methods of the class...



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
            "params": {"user_id": user_id, "other_user_id": "PLACEHOLDER", "date": datetime.date.today().isoformat()}
        })
        return plan

    def _execute_plan(self, plan: List[Dict[str, Any]], prompt: str) -> Dict[str, Any]:
        results = {}
        for step in plan:
            result = self.api_executor.execute(step['api'], step['action'], step['params'])
            results[f"{step['api']}_{step['action']}"] = result
            if step['action'] == 'get_free_slots' and not result.get('success'):
                self.pending_action = 'get_free_slots'
                self.pending_action_contact_id = step['params']['other_user_id']
                break
        return results

    def _generate_response(self, prompt: str, results: Dict[str, Any]) -> Dict[str, Any]:
        if "contacts_find_contact" in results and results["contacts_find_contact"].get("success"):
            if "calendar_get_free_slots" in results and results["calendar_get_free_slots"].get("success"):
                slots = results["calendar_get_free_slots"].get("slots", [])
                if slots:
                    return {"message": "Meeting slots found and processed.", "status": "success"}
                else:
                    return {"message": "There are no available time slots. Would you like to try a different day?", "status": "success"}
            else:
                return {"message": "Failed to find available slots. Please specify a date.", "status": "error"}
        else:
            return {"message": "Failed to find contact.", "status": "error"}

# Example usage
def example_google_calendar_integration():
    credentials_path = 'credentials.json'
    openai_api_key = os.getenv('OPENAI_API_KEY') # Replace with your OpenAI API key

    executor = GoogleCalendarAPIExecutor(credentials_path)
    agent = MeetingBookingMCPAgent(executor, openai_api_key)
    
    result = agent.process_user_prompt("Book a meeting with Chinmay Sir", "primary")
    print("Agent response:")
    print(result)

if __name__ == "__main__":
    example_google_calendar_integration()
