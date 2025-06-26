from langgraph.graph import StateGraph, END
from typing import TypedDict, List
from datetime import datetime, timedelta
import re
from app.calendar_api import get_available_slots, book_appointment

class AgentState(TypedDict):
    messages: List[str]
    intent: str
    date: str
    time: str
    confirmed: bool

def parse_intent(state: AgentState) -> AgentState:
    user_input = state["messages"][-1].lower()
    if "schedule" in user_input or "book" in user_input or "meeting" in user_input:
        state["intent"] = "book_appointment"
    elif "free time" in user_input or "available" in user_input:
        state["intent"] = "check_availability"
    else:
        state["intent"] = "unknown"
    return state

def extract_date_time(state: AgentState) -> AgentState:
    user_input = state["messages"][-1].lower()
    if "tomorrow" in user_input:
        state["date"] = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    elif "friday" in user_input:
        today = datetime.now()
        days_ahead = (4 - today.weekday()) % 7 or 7
        state["date"] = (today + timedelta(days_ahead)).strftime('%Y-%m-%d')
    else:
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', user_input)
        if date_match:
            state["date"] = date_match.group(1)

    time_match = re.search(r'(\d{1,2}:\d{2})', user_input)
    if time_match:
        time_str = time_match.group(1)
        hour, minute = map(int, time_str.split(':'))
        if re.search(r'\bpm\b', user_input) and hour != 12:
            hour += 12
        elif re.search(r'\bam\b', user_input) and hour == 12:
            hour = 0
        state["time"] = f"{hour:02d}:{minute:02d}"
        print(f"Debug: Parsed time from input '{user_input}': {state['time']}")
    elif not state["time"]:  # Apply defaults only if no specific time
        if re.search(r'morning', user_input):
            state["time"] = "09:00"
            print(f"Debug: Applied default morning time: {state['time']}")
        elif re.search(r'afternoon', user_input):
            state["time"] = "14:00"
            print(f"Debug: Applied default afternoon time: {state['time']}")
        elif re.search(r'evening', user_input):
            state["time"] = "18:00"
            print(f"Debug: Applied default evening time: {state['time']}")
    elif state["date"] and not state["time"]:  # Handle full datetime input
        datetime_match = re.search(r'(\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2})', user_input)
        if datetime_match:
            state["date"], state["time"] = datetime_match.group(1).split()
            print(f"Debug: Parsed datetime from input: {state['date']} {state['time']}")
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
        state["messages"].append(f"No available slots on {state['date']}.")
    else:
        state["messages"].append(f"Available slots on {state['date']}: {', '.join(slots)}")
        state["messages"].append("Please choose a time or confirm one of these slots.")
    return state

def book_slot(state: AgentState) -> AgentState:
    if not state["date"] or not state["time"]:
        state["messages"].append("Please provide both date and time to book an appointment.")
        return state
    start_time = f"{state['date']} {state['time']}"
    result = book_appointment(start_time, summary="Meeting")
    if "error" in result:
        state["messages"].append(f"Error: {result['error']}")
    else:
        state["messages"].append(f"Appointment booked successfully at {start_time}!")
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