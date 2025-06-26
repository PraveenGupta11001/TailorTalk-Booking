from app.calendar_api import get_available_slots, book_appointment
import datetime

tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
slots = get_available_slots(tomorrow)
print("Available slots for tomorrow:", slots)

if slots:
    result = book_appointment(slots[0], "Test Meeting")
    print("Booking result:", result)
