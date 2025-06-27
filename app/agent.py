from langgraph.graph import StateGraph, END
from typing import TypedDict, List
from datetime import datetime, timedelta
import re
from app.calendar_api import get_available_slots, book_appointment
from dateutil.parser import parse as parse_date

class AgentState(TypedDict):
    messages: List[str]
    intent: str
    date: str
    time: str
    confirmed: bool

def parse_intent(state: AgentState) -> AgentState:
    user_input = state["messages"][-1].lower()
    if any(keyword in user_input for keyword in ["schedule", "book", "meeting", "appointment"]):
        state["intent"] = "book_appointment"
    elif any(keyword in user_input for keyword in ["free time", "available", "open slots"]):
        state["intent"] = "check_availability"
    else:
        state["intent"] = "unknown"
    return state

def extract_date_time(state: AgentState) -> AgentState:
    user_input = state["messages"][-1].lower()
    today = datetime.now()

    # Date extraction
    if "tomorrow" in user_input:
        state["date"] = (today + timedelta(days=1)).strftime('%Y-%m-%d')
    elif "friday" in user_input:
        days_ahead = (4 - today.weekday()) % 7 or 7
        state["date"] = (today + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
    elif "next week" in user_input:
        days_ahead = 7 + (4 - today.weekday()) % 7
        state["date"] = (today + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
    else:
        try:
            parsed_date = parse_date(user_input, fuzzy=True, default=today)
            state["date"] = parsed_date.strftime('%Y-%m-%d')
        except ValueError:
            state["date"] = None

    # Time extraction
    time_range_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*-\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', user_input)
    single_time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', user_input)

    if time_range_match:
        start_hour, start_min, end_hour, end_min, period = time_range_match.groups()
        start_min = int(start_min or 0)
        end_min = int(end_min or 0)
        start_hour, end_hour = int(start_hour), int(end_hour)

        if period == "pm" and start_hour != 12:
            start_hour += 12
            end_hour += 12
        elif period == "am" and start_hour == 12:
            start_hour = 0
            end_hour = 0 if end_hour == 12 else end_hour

        # Suggest the earliest available slot in the range
        state["time"] = f"{start_hour:02d}:{start_min:02d}"
        state["messages"].append(f"Looking for a slot between {start_hour:02d}:{start_min:02d} and {end_hour:02d}:{end_min:02d}.")
    elif single_time_match:
        hour, minute, period = single_time_match.groups()
        minute = int(minute or 0)
        hour = int(hour)
        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0
        elif hour == 24:  # Handle 24:00 as 00:00
            hour = 0
        state["time"] = f"{hour:02d}:{minute:02d}"
    elif "evening" in user_input:
        state["time"] = "19:00" if "7" in user_input else "18:00"
    elif "afternoon" in user_input:
        state["time"] = "14:00"
    elif "morning" in user_input:
        state["time"] = "09:00"

    # Validate time
    if state["time"]:
        try:
            datetime.strptime(state["time"], '%H:%M')
        except ValueError:
            state["messages"].append("Invalid time format. Please use a valid time (e.g., '3:00 PM' or '15:00').")
            state["time"] = None

    return state

def book_slot(state: AgentState) -> AgentState:
    if not state["date"] or not state["time"]:
        state["messages"].append("Please provide both date and time to book an appointment.")
        return state
    start_time = f"{state['date']} {state['time']}"
    print(f"Debug: Booking start_time before API call: {start_time}")
    result = book_appointment(start_time, summary="Meeting")
    if "error" in result:
        state["messages"].append(f"Error: {result['error']}")
    else:
        # Use the actual booked time from the event (optional, for accuracy)
        state["messages"].append(f"Appointment booked successfully at {start_time}!")
        state["confirmed"] = True
    return state

def check_availability(state: AgentState) -> AgentState:
    if not state["date"]:
        state["messages"].append("Please specify a date (e.g., 'tomorrow', '2025-07-01', or 'Friday').")
        return state
    slots = get_available_slots(state["date"])
    if isinstance(slots, dict) and "error" in slots:
        state["messages"].append(f"Error: {slots['error']}")
    elif not slots:
        state["messages"].append(f"No available slots on {state['date']}. Would you like to try another date?")
    else:
        state["messages"].append(f"Available slots on {state['date']}: {', '.join(slots)}")
        state["messages"].append("Please choose a time (e.g., 'book at 14:00') or let me know if you need other options.")
    return state

def book_slot(state: AgentState) -> AgentState:
    if not state["date"] or not state["time"]:
        state["messages"].append("Please provide both date and time to book an appointment (e.g., '2025-07-01 15:00').")
        return state
    start_time = f"{state['date']} {state['time']}"
    slots = get_available_slots(state["date"])
    if state["time"] not in slots:
        state["messages"].append(f"Sorry, {state['time']} is not available on {state['date']}. Available slots: {', '.join(slots)}")
        return state
    result = book_appointment(start_time, summary="Meeting")
    if "error" in result:
        state["messages"].append(f"Error: {result['error']}")
    else:
        state["messages"].append(f"Appointment booked successfully at {start_time}! Would you like to book another?")
        state["confirmed"] = True
    return state

def handle_unknown(state: AgentState) -> AgentState:
    state["messages"].append("Sorry, I didn't understand. Could you clarify if you want to check availability or book a meeting?")
    return state

def router(state: AgentState) -> str:
    if state["confirmed"]:
        return END
    if state["intent"] == "book_appointment" and not state["time"]:
        return "check_availability"
    elif state["intent"] == "book_appointment" and state["time"]:
        return "book_slot"
    elif state["intent"] == "check_availability":
        return "check_availability"
    else:
        return "handle_unknown"

workflow = StateGraph(AgentState)
workflow.add_node("parse_intent", parse_intent)
workflow.add_node("extract_date_time", extract_date_time)
workflow.add_node("check_availability", check_availability)
workflow.add_node("book_slot", book_slot)
workflow.add_node("handle_unknown", handle_unknown)

workflow.add_edge("parse_intent", "extract_date_time")
workflow.add_conditional_edges(
    "extract_date_time",
    router,
    {
        "check_availability": "check_availability",
        "book_slot": "book_slot",
        "handle_unknown": "handle_unknown",
        END: END
    }
)
workflow.add_edge("check_availability", END)
workflow.add_edge("book_slot", END)
workflow.add_edge("handle_unknown", END)

workflow.set_entry_point("parse_intent")
agent = workflow.compile()

def run_agent(user_input: str) -> List[str]:
    state = {"messages": [user_input], "intent": None, "date": None, "time": None, "confirmed": False}
    result = agent.invoke(state)
    return result["messages"][1:]  # Return responses, excluding user input


if __name__ == "__main__":
    test_inputs = [
        "Hey, I want to schedule a call for tomorrow afternoon.",
        "Do you have any free time this Friday?",
        "Book a meeting at 2025-07-01 15:00"
    ]
    for input_text in test_inputs:
        print(f"Input: {input_text}")
        responses = run_agent(input_text)
        print(f"Responses: {responses}")
        print("---")