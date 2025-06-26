from app.agent import extract_date_time, AgentState
import datetime

test_inputs = [
    "Book a meeting for tomorrow morning at 10:00",
    "Book a meeting for tomorrow morning at 6:00",
    "Schedule a call for tomorrow afternoon at 14:30",
    "Schedule a call for tomorrow evening at 18:30",
    "Book a meeting at 2025-07-01 15:00",
    "Do you have any free time on 2025-07-02",
    "Book a meeting for tomorrow morning",
    "Book a meeting for tomorrow afternoon",
]

for input_text in test_inputs:
    state = {"messages": [input_text], "intent": None, "date": None, "time": None, "confirmed": False}
    result = extract_date_time(state)
    print(f"Input: {input_text}")
    print(f"Parsed Date: {result['date']}")
    print(f"Parsed Time: {result['time']}")
    print("---")