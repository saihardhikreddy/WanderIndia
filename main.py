from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import requests
import json
import os
import re
from datetime import datetime
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from groq import Groq 
from dotenv import load_dotenv

# Load the hidden environment variables from your .env file
load_dotenv()

app = Flask(__name__)

# ==========================================
# CONFIGURATION & API KEYS
# ==========================================
app.secret_key = "wanderindia_super_secret_key_2024"

# 🎯 SECURE KEYS: Pulling from the hidden .env file
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID") 
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")  
GEOAPIFY_KEY = os.getenv("GEOAPIFY_KEY")       
GROQ_API_KEY = os.getenv("GROQ_API_KEY")   

DATABASE_FILE = "history.json"

groq_client = Groq(api_key=GROQ_API_KEY)
GROQ_MODEL = 'llama-3.3-70b-versatile' 

# ==========================================
# LOCAL DATABASE LOGIC
# ==========================================
def load_trips():
    if os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, 'r') as f: 
            return json.load(f)
    return []

def save_trip(trip_data):
    trips = load_trips()
    trips.append(trip_data)
    with open(DATABASE_FILE, 'w') as f: 
        json.dump(trips, f, indent=4)

def get_user_trips(email):
    all_trips = load_trips()
    return [t for t in all_trips if t.get('user_email') == email]

# ==========================================
# AI GENERATION HELPER
# ==========================================
def generate_three_options(source, budget, vibe, excluded_list):
    excluded_text = ", ".join(excluded_list) if excluded_list else "None"
    
    prompt = f"""Act as an expert Indian travel agent. Suggest EXACTLY 3 different travel destinations in India for a "{vibe}" trip departing from {source}. 
    CRITICAL: DO NOT suggest any of these places: {excluded_text}.
    
    You MUST format your response EXACTLY like this template using short, punchy bullet points. Do not use paragraphs. Do not use asterisks (*):
    
    DESTINATION: [City Name]
    WHY: 
    ✨ Vibe: [1 short, exciting sentence describing the atmosphere]
    🏛️ Must-See: [Name 1 top attraction and why it's cool]
    🍛 Local Bite: [Name 1 specific local dish to try]
    WEATHER: Climate: [Type] | Temp: [XX°C to YY°C]
    """
    options = []
    fallback_destinations = ["Jaipur", "Munnar", "Rishikesh", "Udaipur", "Gokarna", "Darjeeling", "Andaman", "Leh Ladakh"]
    
    try:
        completion = groq_client.chat.completions.create(
            model=GROQ_MODEL, messages=[{"role": "user", "content": prompt}], temperature=0.7, max_tokens=1024
        )
        clean_text = completion.choices[0].message.content.replace("*", "")
        
        destinations = re.findall(r"DESTINATION:\s*(.*?)(?:\n|$)", clean_text)
        whys = re.findall(r"WHY:\s*(.*?)(?=\nWEATHER:|\nDESTINATION:|$)", clean_text, re.DOTALL)
        weathers = re.findall(r"WEATHER:\s*(.*?)(?=\nDESTINATION:|$)", clean_text, re.DOTALL)
        
        for i in range(min(len(destinations), 3)):
            # 🎯 FIX: Changed \n to a clean bullet point separator instead of <br> to prevent raw HTML leaking!
            pitch_text = whys[i].strip().replace('\n', ' • ') if i < len(whys) else "✨ Vibe: An incredible journey awaits. • 🏛️ Must-See: Explore the city. • 🍛 Local Bite: Street food."
            weather_text = weathers[i].strip() if i < len(weathers) else "Pleasant"
            options.append({"destination": destinations[i].strip(), "pitch": pitch_text, "cost": f"₹{budget}", "weather": weather_text})
    except Exception: pass

    if len(options) < 3:
        for dest in fallback_destinations:
            if dest not in excluded_list and not any(d.get('destination') == dest for d in options):
                options.append({"destination": dest, "pitch": f"✨ Vibe: Experience the magic of {dest}. • 🏛️ Must-See: Explore the landscapes. • 🍛 Local Bite: Try regional delicacies.", "cost": f"₹{budget}", "weather": "Sunny"})
            if len(options) >= 3: break
                
    for opt in options:
        opt['image_url'] = "https://images.unsplash.com/photo-1524492412937-b28074a5d7da?q=80&w=2000"
        try:
            url = f"https://api.unsplash.com/search/photos?query={opt['destination']}+india+landscape&client_id={UNSPLASH_ACCESS_KEY}&orientation=landscape&per_page=1"
            u_res = requests.get(url)
            if u_res.status_code == 200 and u_res.json()['results']: opt['image_url'] = u_res.json()['results'][0]['urls']['regular']
        except Exception: pass
            
    return options

# ==========================================
# ROUTES
# ==========================================
@app.route('/')
def home():
    if session.get('logged_in'): return redirect(url_for('dashboard'))
    return render_template('login.html', client_id=GOOGLE_CLIENT_ID)

@app.route('/google-login', methods=['POST'])
def google_login():
    try:
        token = request.form.get('credential')
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
        session['logged_in'] = True
        session['user_name'] = idinfo.get('name', 'Traveler')
        session['user_email'] = idinfo.get('email')
        return redirect(url_for('dashboard'))
    except Exception: return "Server error", 500

@app.route('/normal-login', methods=['POST'])
def normal_login():
    session['logged_in'] = True
    session['user_name'] = request.form.get('email', 'Traveler').split('@')[0]
    session['user_email'] = request.form.get('email', 'test@test.com')
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if not session.get('logged_in'): return redirect(url_for('home'))
        
    user_trips = get_user_trips(session.get('user_email'))
    ai_count = len([t for t in user_trips if t.get('mode') == 'recommend'])
    direct_count = len([t for t in user_trips if t.get('mode') == 'direct'])

    if request.method == 'POST':
        form_data = request.form.to_dict()
        action = form_data.get('action')
        source = form_data.get('source', '').strip()
        destination = form_data.get('destination', '').strip()
        budget = form_data.get('budget', '10000')
        vibe = form_data.get('vibe', 'Surprise Me!')
        
        session['current_trip'] = form_data
        session['source_city'] = source
        
        if action == 'direct':
            if not destination: destination = "Goa" 
            prompt = f"Act as a professional Indian travel agent. FORMAT EXACTLY LIKE THIS:\nWHY:\n✨ Vibe: [1 sentence]\n🏛️ Must-See: [1 attraction]\n🍛 Local Bite: [1 dish]\nWEATHER: Climate: [Type] | Temp: [XX°C to YY°C]"
            pitch = "✨ Vibe: An incredible journey awaits. • 🏛️ Must-See: Explore the city. • 🍛 Local Bite: Street food."
            weather_desc = "Pleasant"
            try:
                completion = groq_client.chat.completions.create(model=GROQ_MODEL, messages=[{"role": "user", "content": prompt}], temperature=0.7)
                clean_text = completion.choices[0].message.content.replace("*", "") 
                whys = re.findall(r"WHY:\s*(.*?)(?=\nWEATHER:|$)", clean_text, re.DOTALL)
                weathers = re.findall(r"WEATHER:\s*(.*?)(?=\n|$)", clean_text, re.DOTALL)
                # 🎯 FIX: Changed \n to a clean bullet point separator for the Direct Plan card as well!
                if whys: pitch = whys[0].strip().replace('\n', ' • ')
                if weathers: weather_desc = weathers[0].strip()
            except Exception: pass
            
            card_image = "https://images.unsplash.com/photo-1524492412937-b28074a5d7da?q=80&w=2000"
            try:
                u_res = requests.get(f"https://api.unsplash.com/search/photos?query={destination}+india&client_id={UNSPLASH_ACCESS_KEY}&orientation=landscape&per_page=1")
                if u_res.status_code == 200 and u_res.json()['results']: card_image = u_res.json()['results'][0]['urls']['regular']
            except Exception: pass

            options = [{"destination": destination, "cost": f"₹{budget}", "pitch": pitch, "weather": weather_desc, "image_url": card_image}]
            return render_template('recommendations.html', options=options, form_data=form_data, geoapify_key=GEOAPIFY_KEY)
            
        elif action == 'recommend':
            session['excluded_destinations'] = [] 
            options = generate_three_options(source, budget, vibe, session['excluded_destinations'])
            session['excluded_destinations'].extend([o['destination'] for o in options])
            session.modified = True
            return render_template('recommendations.html', options=options, form_data=form_data, geoapify_key=GEOAPIFY_KEY)
                               
    return render_template('dashboard.html', name=session.get('user_name'), total_trips=len(user_trips), ai_count=ai_count, direct_count=direct_count, form_data={}, geoapify_key=GEOAPIFY_KEY)

@app.route('/regenerate', methods=['POST'])
def regenerate():
    if not session.get('logged_in'): return redirect(url_for('home'))
    form_data = session.get('current_trip', {})
    excluded = session.get('excluded_destinations', [])
    options = generate_three_options(form_data.get('source'), form_data.get('budget'), form_data.get('vibe'), excluded)
    session['excluded_destinations'].extend([o['destination'] for o in options])
    session.modified = True
    return render_template('recommendations.html', options=options, form_data=form_data, geoapify_key=GEOAPIFY_KEY)

@app.route('/generate_itinerary', methods=['POST'])
def generate_itinerary():
    destination = request.form.get('selected_destination', 'Destination')
    trip_data = session.get('current_trip', {})
    source = trip_data.get('source', 'Bangalore')
    budget = trip_data.get('budget', '10000')
    vibe = trip_data.get('vibe', 'Surprise Me!')
    cuisine = trip_data.get('cuisine', 'Local cuisine')
    
    # 🎯 DYNAMIC DAYS FIX: Grabs the duration from your form data. Defaults to 3 if missing.
    try:
        num_days = int(trip_data.get('duration', 3))
    except ValueError:
        num_days = 3 
    
    prompt = f"""Act as an expert local tour guide. Create a CLEAR, SCANNABLE, POINT-WISE {num_days}-day travel itinerary for {destination} from {source}.
    Vibe: {vibe}, Cuisine: {cuisine}. Budget: ₹{budget}.
    
    CRITICAL INSTRUCTIONS:
    1. Generate 4 to 5 bullet points per day (Morning, Lunch, Afternoon, Evening).
    2. Keep descriptions PUNCHY, CONCISE, AND ACTIONABLE. (Maximum 1 to 2 short sentences per point). DO NOT write dense paragraphs.
    3. DO NOT write any paragraphs outside the bullet points.
    4. OUTPUT RAW HTML ONLY. DO NOT include ```html blocks or markdown.
    
    Structure the HTML EXACTLY like this template:
    <div class="day-container" style="margin-bottom: 30px;">
        <h2 style="color: #60a5fa; font-family: 'Playfair Display', serif; font-size: 1.5rem;">Day 1: [Catchy Theme]</h2>
        <ul class="itinerary-list" style="list-style-type: none; padding-left: 0;">
            <li style="margin-bottom: 12px; padding: 16px; background: rgba(30,41,59,0.6); border-radius: 10px; border-left: 4px solid #3b82f6; box-shadow: 0 4px 10px rgba(0,0,0,0.3);">
                <strong style="font-size: 1rem; color: #f8fafc;">🌅 Time - [Location Name]</strong>
                <p style="margin: 6px 0; color: #cbd5e1; font-size: 0.9rem; line-height: 1.5;">[1-2 clear, punchy sentences explaining what to do here].</p>
                <span style="color: #4ade80; font-weight: bold; font-size: 0.85rem;">Cost: ₹[Amount]</span>
            </li>
        </ul>
        <hr style="border: 0; height: 1px; background: rgba(255,255,255,0.1); margin-top: 25px;">
    </div>
    Complete this EXACT HTML structure for {num_days} days."""
    
    itinerary_html = "<h2>Error generating itinerary</h2>"
    try:
        completion = groq_client.chat.completions.create(model=GROQ_MODEL, messages=[{"role": "user", "content": prompt}], temperature=0.7)
        itinerary_html = completion.choices[0].message.content.replace("```html\n", "").replace("```html", "").replace("```", "")
    except Exception as e: print(f"❌ [Groq Error] {e}")

    images = ["https://images.unsplash.com/photo-1524492412937-b28074a5d7da?q=80&w=2000", "https://images.unsplash.com/photo-1472214103451-9374bd1c798e?q=80&w=2000"]
    try:
        u_res = requests.get(f"https://api.unsplash.com/search/photos?query={destination}+india+landscape&client_id={UNSPLASH_ACCESS_KEY}&orientation=landscape&per_page=2")
        if u_res.status_code == 200 and len(u_res.json().get('results', [])) >= 2:
            results = u_res.json()['results']
            images = [results[0]['urls']['regular'], results[1]['urls']['regular']]
    except Exception: pass

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    new_trip = {
        "user_email": session.get('user_email'), "destination": destination, "source": source,
        "start_date": trip_data.get('start_date', ''), "end_date": trip_data.get('end_date', ''), 
        "budget": budget, "mode": trip_data.get('action', 'recommend'), 
        "created_at": created_at, "itinerary_html": itinerary_html, "images": images
    }
    save_trip(new_trip)

    session['current_trip'] = {
        "source": source, "destination": destination, "budget": budget, "vibe": vibe,
        "duration": num_days, "created_at": created_at
    }

    return render_template('itinerary.html', destination=destination, source=source, images=images, itinerary_html=itinerary_html, geoapify_key=GEOAPIFY_KEY)

@app.route('/history')
def history():
    if not session.get('logged_in'): return redirect(url_for('home'))
    user_trips = get_user_trips(session.get('user_email'))
    user_trips.reverse() 
    return render_template('history.html', trips=user_trips)

@app.route('/revisit_trip', methods=['POST'])
def revisit_trip():
    form_data = request.form.to_dict()
    created_at = form_data.get('created_at')
    
    trips = get_user_trips(session.get('user_email'))
    for t in trips:
        if t.get('created_at') == created_at and t.get('itinerary_html'):
            session['current_trip'] = {
                "source": t['source'], "destination": t['destination'], "created_at": created_at
            }
            return render_template('itinerary.html', destination=t['destination'], source=t['source'], images=t.get('images', []), itinerary_html=t['itinerary_html'], geoapify_key=GEOAPIFY_KEY)
            
    return redirect(url_for('history'))

@app.route('/on_the_go')
def on_the_go():
    trip = session.get('current_trip', {})
    return render_template('on_the_go.html', 
                           source=trip.get('source', 'Bangalore'), 
                           destination=trip.get('destination', 'Goa'), 
                           geoapify_key=GEOAPIFY_KEY)

@app.route('/api/get_pitstops', methods=['POST'])
def get_pitstops():
    try:
        data = request.json
        source = data.get('source')
        destination = data.get('destination')
        place_type = data.get('type', 'tourist attractions')
        
        prompt = f"""A driver is traveling on the best route and the fastest route from {source} to {destination} in India. 
        Identify exactly 15 specific, highly-rated {place_type} physically located in towns directly on this highway. 
        CRITICAL: Distribute them evenly across the ENTIRE journey (beginning, middle, and end).
        make sure that the places are physically located in towns directly on this highway,and they are on the way only.
        dont include any places that are not on the way.
        Do not include {source} or {destination}. 
        Return ONLY a comma-separated list of the 15 names, with no extra text."""
        
        completion = groq_client.chat.completions.create(model=GROQ_MODEL, messages=[{"role": "user", "content": prompt}], temperature=0.1)
        places = [p.strip() for p in completion.choices[0].message.content.replace('"', '').replace("'", "").split(',') if p.strip()]
        
        return jsonify({"success": True, "stops": places})
    except Exception as e:
        return jsonify({"success": False, "stops": []})

if __name__ == '__main__':
    app.run(port=8000, debug=True, use_reloader=False)