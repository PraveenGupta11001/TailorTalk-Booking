from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Optional
from datetime import datetime, timedelta
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
        state["messages"].append("I need to know the date for your appointment. Could you specify that first?")
        return state
    
    if not state["time"]:
        if state["retry_count"] > 2:
            state["messages"].append("I'm having trouble understanding the time. Could you please specify a time like '2pm', '14:00', or 'in the morning'?")
            return state
        
        state["messages"].append("What time would you like to book? (e.g., '2pm', '14:00', or 'in the morning')")
        return state
    
    # Validate time format
    try:
        datetime.strptime(state["time"], '%H:%M')
    except ValueError:
        state["messages"].append("That time format doesn't look right. Please use formats like '2pm', '14:00', or 'in the morning'.")
        state["time"] = None
        return state
    
    slots = get_available_slots(state["date"])
    if isinstance(slots, dict) and "error" in slots:
        state["messages"].append(f"Sorry, I couldn't check availability: {slots['error']}")
        return state
    
    if state["time"] not in slots:
        # Find the closest available time
        target_h, target_m = map(int, state["time"].split(':'))
        target_min = target_h * 60 + target_m
        
        closest_slot = None
        min_diff = float('inf')
        
        for slot in slots:
            h, m = map(int, slot.split(':'))
            slot_min = h * 60 + m
            diff = abs(slot_min - target_min)
            
            if diff < min_diff:
                min_diff = diff
                closest_slot = slot
        
        if closest_slot:
            state["messages"].append(
                f"Sorry, {state['time']} isn't available on {state['date']}. "
                f"The closest available time is {closest_slot}. Would you like to book that instead? "
                f"(Or say 'no' to choose another time)"
            )
            # Store the suggested time for easy confirmation
            state["suggested_time"] = closest_slot
        else:
            state["messages"].append(
                f"Sorry, {state['time']} isn't available on {state['date']} and I couldn't find a close alternative. "
                f"Would you like to try another time or day?"
            )
        return state
    
    # If we get here, the slot is available
    start_time = f"{state['date']} {state['time']}"
    result = book_appointment(start_time, summary="Meeting")
    
    if "error" in result:
        state["messages"].append(f"❌ Failed to book: {result['error']}")
    else:
        # Verify the booked time matches requested time
        booked_start = datetime.datetime.strptime(result['start'], '%Y-%m-%d %H:%M')
        requested_start = datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M')
        
        if booked_start != requested_start:
            state["messages"].append(
                f"⚠️ Warning: Calendar system adjusted our booking time.\n"
                f"Requested: {requested_start.strftime('%I:%M %p')}\n"
                f"Booked: {booked_start.strftime('%I:%M %p')}\n"
                f"Should we try again or pick another time?"
            )
        else:
            state["messages"].append(
                f"✅ Confirmed! Booked exactly at {booked_start.strftime('%I:%M %p')} "
                f"on {booked_start.strftime('%A, %B %d')}."
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
    
    # Check for confirmation of suggested time
    if "suggested_time" in state and state["messages"][-1].lower() in ["yes", "y", "ok", "sure"]:
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