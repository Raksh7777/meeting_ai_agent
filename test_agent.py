import json
import os
import openai
from google_calendar_integration_openai import GoogleCalendarAPIExecutor
from meeting_booking_agent import MeetingBookingMCPAgent
from dotenv import load_dotenv

load_dotenv()


def test_meeting_booking_agent():
    """
    Function to test the meeting booking agent with Google Calendar integration
    """
    print("=== Meeting Booking Agent Test ===")
    
    # Path to your OAuth credentials file from Google Cloud Console
    credentials_path = 'credentials.json'
    
    # Check if credentials file exists
    if not os.path.exists(credentials_path):
        print(f"Error: Credentials file '{credentials_path}' not found.")
        print("Please download the OAuth credentials JSON from Google Cloud Console.")
        return
    
    # Retrieve OpenAI API key from environment or configuration
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        print("Error: OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        return
    
    try:
        # Create the Google Calendar API executor
        print("Initializing Google Calendar API executor...")
        executor = GoogleCalendarAPIExecutor(credentials_path)
        
        # Create the MCP agent with the Google Calendar executor and OpenAI API key
        print("Initializing Meeting Booking MCP Agent...")
        agent = MeetingBookingMCPAgent(executor, openai_api_key)
        
        # Interactive testing loop
        print("\nEnter prompts to test the agent. Type 'exit' to quit.")
        print("Example: 'Book a meeting with John'")
        
        while True:
            # Get user prompt
            prompt = input("\nYour prompt: ")
            
            if prompt.lower() in ["exit", "quit", "q"]:
                break
            
            # Process the prompt (using 'primary' as the user_id for Google Calendar)
            print("\nProcessing prompt...")
            result = agent.process_user_prompt(prompt, "primary")
            
            # Display the result
            print("\nAgent response:")
            print(json.dumps(result, indent=2))
            
            # If meeting was booked successfully, show details
            if result.get("status") == "success" and "meeting" in result:
                print("\nMeeting details:")
                print(f"Title: {result['meeting']['title']}")
                print(f"Time: {result['meeting']['start_time']} to {result['meeting']['end_time']}")
                if "alternative_slots" in result and result["alternative_slots"]:
                    print("\nAlternative slots:")
                    for i, slot in enumerate(result["alternative_slots"]):
                        try:
                            start = datetime.datetime.fromisoformat(slot["start_time"].replace('Z', '+00:00'))
                            end = datetime.datetime.fromisoformat(slot["end_time"].replace('Z', '+00:00'))
                            print(f"{i+1}. {start.strftime('%I:%M %p')} to {end.strftime('%I:%M %p')}")
                        except:
                            print(f"{i+1}. {slot['start_time']} to {slot['end_time']}")
    
    except Exception as e:
        print(f"\nError during testing: {str(e)}")

if __name__ == "__main__":
    test_meeting_booking_agent()
