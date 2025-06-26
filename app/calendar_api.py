from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import datetime
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from pytz import utc, timezone

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
        ist = timezone('Asia/Kolkata')
        start_date = datetime.datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=ist)
        end_date = start_date + datetime.timedelta(days=1)
        start_time = start_date.replace(hour=9, minute=0, tzinfo=ist).astimezone(utc).isoformat() + 'Z'
        end_time = start_date.replace(hour=17, minute=0, tzinfo=ist).astimezone(utc).isoformat() + 'Z'

        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_time,
            timeMax=end_time,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        available_slots = []
        current_time = start_date.replace(hour=9, minute=0, tzinfo=ist)
        while current_time < start_date.replace(hour=17, minute=0, tzinfo=ist):
            slot_end = current_time + datetime.timedelta(minutes=duration)
            is_available = True
            for event in events:
                event_start = datetime.datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00')).replace(tzinfo=utc).astimezone(ist)
                event_end = datetime.datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00')).replace(tzinfo=utc).astimezone(ist)
                if not (slot_end <= event_start or current_time >= event_end):
                    is_available = False
                    break
            if is_available:
                available_slots.append(current_time.strftime('%Y-%m-%d %H:%M'))
            current_time += datetime.timedelta(minutes=duration)
        return available_slots
    except Exception as e:
        return {"error": str(e)}

def book_appointment(start_time: str, summary: str, duration: int = 60):
    try:
        service = get_calendar_service()
        ist = timezone('Asia/Kolkata')
        start_dt = ist.localize(datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M'))
        end_dt = start_dt + datetime.timedelta(minutes=duration)
        
        event = {
            'summary': summary,
            'start': {
                'dateTime': start_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': 'Asia/Kolkata'
            },
            'end': {
                'dateTime': end_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': 'Asia/Kolkata'
            },
        }
        print(f"Debug: Event data: {event}")
        event = service.events().insert(calendarId='primary', body=event).execute()
        return {"status": "success", "event_id": event.get('id')}
    except HttpError as e:
        print(f"Debug: HttpError details: {str(e)}")
        return {"error": f"Failed to book appointment: {str(e)}"}
