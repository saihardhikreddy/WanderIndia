# 🌍 Wanderindia: Smart Travel Planner

Wanderindia is a full-stack, AI-powered travel planning application designed to generate highly detailed itineraries and provide real-time, interactive highway scanning for road trips across India. 

Built with a sleek Glassmorphism UI, Wanderindia combines the creative power of Large Language Models (LLMs) with high-density satellite mapping APIs to ensure users never miss a scenic spot, highly-rated dhaba, or essential fuel stop.

---

## ✨ Features

* **🔐 Secure Authentication:** Integrated Google OAuth 2.0 for seamless, one-click user logins.
* **🤖 AI Itinerary Generation:** Powered by Groq (Llama-3), generating dense, scannable, and actionable day-by-day travel plans based on budget, vibe, and duration.
* **🗺️ "On The Go" Live Navigator:** An interactive Leaflet map that draws exact highway routes between Indian cities using Geoapify.
* **📡 High-Density Route Scanner:** Mathematically samples points along your driving route and queries the Geoapify Places API to find Stays, Food, Fuel, and Attractions strictly on the highway.
* **🛡️ Mathematical Geofencing:** Prevents map clutter by calculating a 15km exclusion zone around your starting and ending cities.
* **📍 Smart Google Maps Integration:** Compiles verified, officially named places into a dynamic Google Maps Directions URL for flawless real-world navigation.
* **📄 Export & Download:** Users can download their AI itineraries as stylized PDFs or take high-res snapshot PNGs of their live route maps.

---

## 🛠️ Tech Stack

* Backend: Python, Flask
* Frontend: HTML5, TailwindCSS, JavaScript (ES6)
* AI Engine: Groq API (Llama-3.3-70b-versatile)
* Mapping & Geocoding: Leaflet.js, Geoapify Routing & Places API
* Authentication: Google Identity Services
* Imagery: Unsplash API
* Utilities: html2pdf.js, html2canvas

---

## 🚀 Installation & Setup

### 1. Clone the repository
git clone https://github.com/YourUsername/wanderindia.git
cd wanderindia

### 2. Create a virtual environment (Recommended)

For macOS/Linux:
python3 -m venv venv
source venv/bin/activate

For Windows:
python -m venv venv
venv\Scripts\activate

### 3. Install dependencies
pip install Flask requests google-auth google-auth-oauthlib groq

### 4. Configure API Keys
Open main.py and replace the placeholder API keys with your own. 
(Note: For production environments, it is highly recommended to move these to a hidden .env file to prevent exposing them to the public).

* Google Client ID (For OAuth login)
* Unsplash Access Key (For destination imagery)
* Geoapify API Key (For mapping and routing)
* Groq API Key (For AI generation)

### 5. Run the application
python main.py

Open your web browser and navigate to http://localhost:8000. 
(Important: Always use localhost instead of 127.0.0.1 to ensure Google OAuth authentication works correctly).

---

## 📂 Project Structure

wanderindia/
│
├── main.py                   # Core Flask application and backend routing logic
├── history.json              # Local JSON database for user trip history
│
└── templates/
    ├── login.html            # Google OAuth login portal
    ├── dashboard.html        # Main user dashboard and trip planner form
    ├── recommendations.html  # AI-generated destination suggestions
    ├── itinerary.html        # Detailed daily itinerary with PDF export
    ├── on_the_go.html        # Live map scanner with Geoapify integration
    └── history.html          # User's past generated trips

---

## 📝 License

This project is licensed under the MIT License.