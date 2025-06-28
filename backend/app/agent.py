from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))
import re
from app.calendar_api import get_available_slots, book_appointment
from dateutil.parser import parse as parse_date
from dateutil.relativedelta import relativedelta

class AgentState(TypedDict):
    messages: List[str]
    intent: str
    date: Optional[str]
    time: Optional[str]
    confirmed: bool
    retry_count: int

def parse_intent(state: AgentState) -> AgentState:
    user_input = state["messages"][-1].lower()
    if any(keyword in user_input for keyword in ["schedule", "book", "meeting", "appointment", "reserve"]):
        state["intent"] = "book_appointment"
    elif any(keyword in user_input for keyword in ["free time", "available", "open slots", "availability"]):
        state["intent"] = "check_availability"
    else:
        state["intent"] = "unknown"
    return state

def extract_date_time(state: AgentState) -> AgentState:
    user_input = state["messages"][-1].lower()
    today = datetime.now()
    state["retry_count"] = state.get("retry_count", 0) + 1

    # Enhanced date extraction
    date_keywords = {
        "today": today,
        "tomorrow": today + timedelta(days=1),
        "monday": today + timedelta(days=(0 - today.weekday()) % 7),
        "tuesday": today + timedelta(days=(1 - today.weekday()) % 7),
        "wednesday": today + timedelta(days=(2 - today.weekday()) % 7),
        "thursday": today + timedelta(days=(3 - today.weekday()) % 7),
        "friday": today + timedelta(days=(4 - today.weekday()) % 7),
        "saturday": today + timedelta(days=(5 - today.weekday()) % 7),
        "sunday": today + timedelta(days=(6 - today.weekday()) % 7),
        "next week": today + timedelta(weeks=1),
        "next month": today + relativedelta(months=+1)
    }

    for keyword, date_value in date_keywords.items():
        if keyword in user_input:
            state["date"] = date_value.strftime('%Y-%m-%d')
            break
    else:
        try:
            parsed_date = parse_date(user_input, fuzzy=True, default=today)
            if parsed_date != today or any(word in user_input for word in ["today", "now"]):
                state["date"] = parsed_date.strftime('%Y-%m-%d')
        except ValueError:
            pass

    # Enhanced time extraction with better period handling
    time_periods = {
        "morning": "09:00",
        "afternoon": "14:00",
        "evening": "18:00",
        "night": "20:00"
    }

    for period, default_time in time_periods.items():
        if period in user_input:
            state["time"] = default_time

    # Handle explicit time formats
    time_formats = [
        (r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', 1),  # 3pm, 11:30am
        (r'(\d{1,2})\s*(am|pm)', 1),               # 6 pm
        (r'(\d{1,2}):(\d{2})', 0),                 # 15:00
        (r'(\d{1,2})', 0)                          # 14 (assuming 24h format)
    ]

    for pattern, has_period in time_formats:
        match = re.search(pattern, user_input, re.IGNORECASE)
        if match:
            groups = match.groups()
            hour = int(groups[0])
            minute = int(groups[1]) if len(groups) > 1 and groups[1] else 0
            
            if has_period and groups[-1]:
                period = groups[-1].lower()
                if period == "pm" and hour != 12:
                    hour += 12
                elif period == "am" and hour == 12:
                    hour = 0
            
            # Validate hour
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                state["time"] = f"{hour:02d}:{minute:02d}"
                break

    return state

def check_availability(state: AgentState) -> AgentState:
    if not state["date"]:
        if state["retry_count"] > 2:
            state["messages"].append("I'm having trouble understanding the date. Could you please specify a date like 'tomorrow', 'Friday', or 'July 15th'?")
            return state
        
        state["messages"].append("When would you like to check availability for? (e.g., 'tomorrow', 'Friday', or 'July 15th')")
        return state
    
    slots = get_available_slots(state["date"])
    if isinstance(slots, dict) and "error" in slots:
        state["messages"].append(f"Sorry, I couldn't check availability: {slots['error']}")
    elif not slots:
        state["messages"].append(f"Sorry, I'm completely booked on {state['date']}. Would you like to try another day?")
    else:
        # Group slots for better readability
        morning_slots = [s for s in slots if int(s.split(':')[0]) < 12]
        afternoon_slots = [s for s in slots if 12 <= int(s.split(':')[0]) < 17]
        evening_slots = [s for s in slots if int(s.split(':')[0]) >= 17]
        
        response = f"Here's my availability on {state['date']}:\n"
        if morning_slots:
            response += f"☀️ Morning: {', '.join(morning_slots)}\n"
        if afternoon_slots:
            response += f"🌞 Afternoon: {', '.join(afternoon_slots)}\n"
        if evening_slots:
            response += f"🌙 Evening: {', '.join(evening_slots)}\n"
        
        response += "\nPlease let me know which time works best for you or if you'd like to check another day."
        state["messages"].append(response)
    
    return state

def book_slot(state: AgentState) -> AgentState:
    if not state["date"]:
        state["messages"].append("Please specify a date first.")
        return state
    
    if not state["time"]:
        state["messages"].append("What time would you like to book?")
        return state
    
    # Parse the requested time
    try:
        requested_time = datetime.strptime(f"{state['date']} {state['time']}", '%Y-%m-%d %H:%M')
    except ValueError:
        state["messages"].append("Invalid time format. Please use HH:MM format.")
        return state
    
    # Check availability
    slots = get_available_slots(state["date"])
    if isinstance(slots, dict) and "error" in slots:
        state["messages"].append(f"Error checking availability: {slots['error']}")
        return state
    
    # Convert available slots to datetime objects for comparison
    available_times = [
        datetime.strptime(f"{state['date']} {slot}", '%Y-%m-%d %H:%M')
        for slot in slots
    ]
    
    # Find exact or nearest available slot
    if requested_time in available_times:
        # Exact match available
        result = book_appointment(f"{state['date']} {state['time']}", "Meeting")
    else:
        # Find nearest available time
        time_diffs = [(abs((rt - requested_time).total_seconds()), rt) for rt in available_times]
        time_diffs.sort()
        closest_time = time_diffs[0][1] if time_diffs else None
        
        if closest_time:
            state["messages"].append(
                f"Sorry, {state['time']} isn't available. "
                f"The closest available time is {closest_time.strftime('%H:%M')}. "
                f"Would you like to book that instead?"
            )
            state["suggested_time"] = closest_time.strftime('%H:%M')
            return state
        else:
            state["messages"].append("No available slots for that day.")
            return state
    
    # Handle booking result
    if "error" in result:
        state["messages"].append(f"Booking failed: {result['error']}")
    else:
        state["messages"].append(
            f"✅ Booked successfully at {result['start']}!"
        )
        state["confirmed"] = True
    
    return state

def handle_unknown(state: AgentState) -> AgentState:
    if state["retry_count"] > 2:
        state["messages"].append("I'm having trouble understanding. Would you like to check availability or book an appointment?")
    else:
        state["messages"].append("I'm here to help you book appointments. You can say things like:")
        state["messages"].append("- 'I'd like to book a meeting tomorrow at 2pm'")
        state["messages"].append("- 'What's available next Tuesday?'")
        state["messages"].append("- 'Schedule a call for Friday afternoon'")
    return state

def router(state: AgentState) -> str:
    if state["confirmed"]:
        return END
    
    # Handle suggested time confirmations
    if "suggested_time" in state and state["messages"][-1].lower() in ["yes", "y", "ok"]:
        state["time"] = state["suggested_time"]
        del state["suggested_time"]
        return "book_slot"
    
    if state["intent"] == "book_appointment":
        if not state["date"] or not state["time"]:
            return "check_availability"
        return "book_slot"
    elif state["intent"] == "check_availability":
        return "check_availability"
    else:
        return "handle_unknown"

# Build the workflow
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
    state = {
        "messages": [user_input],
        "intent": None,
        "date": None,
        "time": None,
        "confirmed": False,
        "retry_count": 0
    }
    result = agent.invoke(state)
    return result["messages"][1:]  # Return responses, excluding user input