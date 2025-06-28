from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import datetime
import os.path
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from pytz import timezone
from datetime import datetime, timedelta
import pytz

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(os.environ.get("GOOGLE_CREDENTIALS"), SCOPES)
            print(os.environ.get("GOOGLE_CREDENTIALS"))
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)



def get_available_slots(date: str, duration: int = 60):
    try:
        service = get_calendar_service()
        tz = pytz.timezone('Asia/Kolkata')
        
        # Parse date and set time bounds (proper timezone handling)
        naive_date = datetime.strptime(date, '%Y-%m-%d')
        start_date = tz.localize(naive_date.replace(hour=0, minute=0, second=0))
        end_date = tz.localize(naive_date.replace(hour=23, minute=59, second=59))
        
        # Format time bounds correctly for API
        time_min = start_date.isoformat()
        time_max = end_date.isoformat()

        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        available_slots = []
        current_time = start_date

        while current_time < end_date:
            slot_end = current_time + timedelta(minutes=duration)
            
            # Skip non-hourly slots if you want only exact hours
            if current_time.minute != 0:
                current_time = current_time.replace(minute=0) + timedelta(hours=1)
                continue

            is_available = True
            for event in events:
                event_start = event['start'].get('dateTime') or event['start'].get('date')
                event_end = event['end'].get('dateTime') or event['end'].get('date')
                
                if 'date' in event['start']:  # All-day event
                    event_date = datetime.strptime(event_start, '%Y-%m-%d').date()
                    if event_date == start_date.date():
                        is_available = False
                        break
                else:  # Timed event
                    event_start_dt = datetime.fromisoformat(event_start.replace('Z', '+00:00')).astimezone(tz)
                    event_end_dt = datetime.fromisoformat(event_end.replace('Z', '+00:00')).astimezone(tz)
                    if not (slot_end <= event_start_dt or current_time >= event_end_dt):
                        is_available = False
                        break

            if is_available:
                available_slots.append(current_time.strftime('%H:%M'))
            
            current_time += timedelta(hours=1)

        return available_slots

    except HttpError as e:
        return {"error": f"Calendar API error: {str(e)}"}
    except Exception as e:
        return {"error": f"Error checking availability: {str(e)}"}

def book_appointment(start_time: str, summary: str, duration: int = 60):
    try:
        service = get_calendar_service()
        tz = pytz.timezone('Asia/Kolkata')
        
        # Strict time parsing with validation
        try:
            naive_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M')
            if not (0 <= naive_dt.hour < 24 and 0 <= naive_dt.minute < 60):
                return {"error": "Invalid time - must be between 00:00 and 23:59"}
                
            start_dt = tz.localize(naive_dt.replace(
                minute=0,  # Force exact hour
                second=0,
                microsecond=0
            ))
        except ValueError as e:
            return {"error": f"Invalid time format: {str(e)}"}

        # Calculate end time (strict 1-hour duration)
        end_dt = start_dt + timedelta(hours=1)  # Changed from minutes=duration for exact hours

        # Verify times
        print(f"DEBUG: Booking from {start_dt} to {end_dt}")  # For verification
        
        event = {
            'summary': summary,
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': 'Asia/Kolkata',
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': 'Asia/Kolkata',
            },
            'reminders': {
                'useDefault': True,
            }
        }

        created_event = service.events().insert(
            calendarId='primary',
            body=event
        ).execute()

        # Verify the actual booked times
        booked_start = datetime.fromisoformat(created_event['start']['dateTime']).astimezone(tz)
        booked_end = datetime.fromisoformat(created_event['end']['dateTime']).astimezone(tz)
        
        return {
            "status": "success",
            "event_id": created_event.get('id'),
            "start": booked_start.strftime('%Y-%m-%d %H:%M'),
            "end": booked_end.strftime('%Y-%m-%d %H:%M'),
            "duration_hours": (booked_end - booked_start).total_seconds() / 3600
        }

    except HttpError as e:
        return {"error": f"Calendar API error: {str(e)}"}
    except Exception as e:
        return {"error": f"Booking failed: {str(e)}"}