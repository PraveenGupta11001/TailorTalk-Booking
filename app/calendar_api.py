from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import datetime
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from pytz import timezone

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)

def get_available_slots(date: str, duration: int = 60):
    try:
        service = get_calendar_service()
        tz = timezone('Asia/Kolkata')
        start_date = datetime.datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=tz)
        
        # Extended working hours (8am to 8pm)
        start_time = start_date.replace(hour=8, minute=0, tzinfo=tz).isoformat()
        end_time = start_date.replace(hour=20, minute=0, tzinfo=tz).isoformat()

        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_time,
            timeMax=end_time,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        available_slots = []
        # Start at the top of each hour
        current_time = start_date.replace(hour=8, minute=0, second=0, microsecond=0, tzinfo=tz)
        end_of_day = start_date.replace(hour=20, minute=0, tzinfo=tz)

        while current_time < end_of_day:
            slot_end = current_time + datetime.timedelta(minutes=duration)
            is_available = True

            if current_time.minute != 0:
                current_time = current_time.replace(minute=0) + datetime.timedelta(hours=1)
                continue
            
            for event in events:
                event_start_str = event['start'].get('dateTime', event['start'].get('date'))
                event_end_str = event['end'].get('dateTime', event['end'].get('date'))
                
                if 'date' in event['start']:  # All-day event
                    event_start = datetime.datetime.strptime(event_start_str, '%Y-%m-%d').replace(tzinfo=tz)
                    event_end = datetime.datetime.strptime(event_end_str, '%Y-%m-%d').replace(tzinfo=tz)
                    if event_start.date() == start_date.date():
                        is_available = False
                        break
                else:  # Timed event
                    event_start = datetime.datetime.fromisoformat(event_start_str.replace('Z', '+00:00')).astimezone(tz)
                    event_end = datetime.datetime.fromisoformat(event_end_str.replace('Z', '+00:00')).astimezone(tz)
                    if not (slot_end <= event_start or current_time >= event_end):
                        is_available = False
                        break
            
            if is_available:
                available_slots.append(current_time.strftime('%H:%M'))
            
            # Move to next hour or specified interval
            current_time += datetime.timedelta(hours=1)  # Changed from minutes=30 to hours=1

        return available_slots
    except Exception as e:
        return {"error": str(e)}

def book_appointment(start_time: str, summary: str, duration: int = 60):
    try:
        service = get_calendar_service()
        tz = timezone('Asia/Kolkata')
        
        # STRICT time parsing - forces exact hour/minute
        try:
            start_dt = datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M')
            start_dt = tz.localize(start_dt.replace(
                minute=0,  # Force to exact hour
                second=0,
                microsecond=0
            ))
        except ValueError as e:
            return {"error": f"Invalid time format: {str(e)}. Please use format 'YYYY-MM-DD HH:MM'"}

        # Validate time is within working hours (8am-8pm)
        if not (8 <= start_dt.hour < 20):
            return {"error": "Meetings can only be scheduled between 8am and 8pm"}
        
        end_dt = start_dt + datetime.timedelta(minutes=duration)

        # Double-check availability (exact match required)
        slots = get_available_slots(start_dt.strftime('%Y-%m-%d'))
        if isinstance(slots, dict):
            return slots
        if start_dt.strftime('%H:%M') not in slots:
            return {"error": "That exact time slot is no longer available"}

        # Create event with STRICT time formatting
        event = {
            'summary': summary,
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': str(tz),
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': str(tz),
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 30}
                ]
            }
        }

        # DEBUG: Print exact times being sent to Google
        print(f"DEBUG: Booking event from {start_dt} to {end_dt}")
        
        event = service.events().insert(
            calendarId='primary',
            body=event,
            # These parameters force exact times
            supportsAttachments=False,
            conferenceDataVersion=0
        ).execute()

        # Verify the booked times
        booked_start = datetime.datetime.fromisoformat(event['start']['dateTime'])
        booked_end = datetime.datetime.fromisoformat(event['end']['dateTime'])
        if booked_start != start_dt or booked_end != end_dt:
            # Immediately delete if times were modified
            service.events().delete(calendarId='primary', eventId=event['id']).execute()
            return {"error": "Calendar modified our requested times - please try again"}

        return {
            "status": "success",
            "event_id": event.get('id'),
            "htmlLink": event.get('htmlLink'),
            "start": booked_start.strftime('%Y-%m-%d %H:%M'),
            "end": booked_end.strftime('%Y-%m-%d %H:%M')
        }
    except Exception as e:
        return {"error": f"Booking failed: {str(e)}"}