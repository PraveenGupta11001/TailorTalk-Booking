import os
import json
import base64
import pytz
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ['https://www.googleapis.com/auth/calendar']


def decode_and_write_file(env_var_name, filename):
    data = os.getenv(env_var_name)
    if not data:
        raise Exception(f"{env_var_name} not set in environment.")
    decoded = base64.b64decode(data).decode("utf-8")
    with open(filename, "w") as f:
        f.write(decoded)


def get_calendar_service():
    decode_and_write_file("GOOGLE_CREDENTIALS_BASE64", "credentials.json")
    decode_and_write_file("GOOGLE_TOKEN_BASE64", "token.json")

    creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise Exception("Invalid or expired Google credentials.")

    return build('calendar', 'v3', credentials=creds)


def get_available_slots(date: str, duration: int = 60):
    try:
        service = get_calendar_service()
        tz = pytz.timezone('Asia/Kolkata')

        # Full day range
        naive_date = datetime.strptime(date, '%Y-%m-%d')
        start_date = tz.localize(naive_date.replace(hour=0, minute=0, second=0))
        end_date = tz.localize(naive_date.replace(hour=23, minute=59, second=59))

        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_date.isoformat(),
            timeMax=end_date.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        available_slots = []
        current_time = start_date

        while current_time < end_date:
            slot_end = current_time + timedelta(minutes=duration)

            # Only check full hour slots
            if current_time.minute != 0:
                current_time = current_time.replace(minute=0) + timedelta(hours=1)
                continue

            is_available = True
            for event in events:
                event_start = event['start'].get('dateTime') or event['start'].get('date')
                event_end = event['end'].get('dateTime') or event['end'].get('date')

                if 'date' in event['start']:
                    if datetime.strptime(event_start, '%Y-%m-%d').date() == current_time.date():
                        is_available = False
                        break
                else:
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

        # Parse and round time
        naive_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M')
        start_dt = tz.localize(naive_dt.replace(minute=0, second=0, microsecond=0))
        end_dt = start_dt + timedelta(minutes=duration)

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

        created_event = service.events().insert(calendarId='primary', body=event).execute()

        return {
            "status": "success",
            "event_id": created_event.get('id'),
            "start": start_dt.strftime('%Y-%m-%d %H:%M'),
            "end": end_dt.strftime('%Y-%m-%d %H:%M'),
            "duration_hours": (end_dt - start_dt).total_seconds() / 3600
        }

    except HttpError as e:
        return {"error": f"Calendar API error: {str(e)}"}
    except Exception as e:
        return {"error": f"Booking failed: {str(e)}"}
