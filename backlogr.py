# External imports
import streamlit as st
import requests
import urllib.parse
import sqlite3

# Steam OAuth Configuration
STEAM_OPENID_URL = "https://steamcommunity.com/openid/login"
REDIRECT_URI = "http://localhost:8501"  # Replace with your Streamlit app's URL
STEAM_API_KEY = "0E946B515504AE10AE711984A10A7AE2"  # Replace with your Steam API Key

# Construct the OpenID request URL
def authenticate_with_steam():
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": REDIRECT_URI,
        "openid.realm": REDIRECT_URI,
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    auth_url = f"{STEAM_OPENID_URL}?" + urllib.parse.urlencode(params)
    return auth_url

# Validate Steam OpenID login
def verify_steam_login(query_params):
    validation_url = "https://steamcommunity.com/openid/login"
    query_params["openid.mode"] = "check_authentication"
    response = requests.post(validation_url, data=query_params)

    # Check if the response is valid
    if "is_valid:true" in response.text:
        claimed_id = query_params.get("openid.claimed_id")
        if claimed_id and isinstance(claimed_id, list):
            claimed_id = claimed_id[0]  # Extract the first element if it's a list
        if claimed_id:
            steam_id = claimed_id.split("/")[-1]  # Extract SteamID from claimed_id URL
            return steam_id
    return None

# Fetch user's Steam library
def fetch_steam_library(steam_id):
    url = "http://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
    params = {
        "key": STEAM_API_KEY,
        "steamid": steam_id,
        "include_appinfo": True,
    }
    response = requests.get(url, params=params)
    if response.ok:
        return response.json().get("response", {}).get("games", [])
    return []

# Initialize session state
if "steam_id" not in st.session_state:
    st.session_state.steam_id = None

# Streamlit App
st.title("Backlogr")

# Login button and redirection
if st.session_state.steam_id is None:
    st.write("To start tracking your backlog, log in with your Steam account.")
    
    if st.button("Login with Steam"):
        auth_url = authenticate_with_steam()
        st.markdown(f"[Click here to authenticate with Steam]({auth_url})", unsafe_allow_html=True)

    # Handle the OpenID callback after redirection
    query_params = st.query_params
    if query_params:
        if "openid.ns" in query_params:
            steam_id = verify_steam_login(query_params)
            if steam_id:
                st.session_state.steam_id = steam_id
                st.success(f"Logged in successfully! Steam ID: {steam_id}")
            else:
                st.error("Steam login failed. Please try again.")
else:
    st.write(f"Logged in as Steam ID: {st.session_state.steam_id}")

# Display Steam library if logged in
if st.session_state.steam_id:
    st.write("Fetching your Steam library...")
    library = fetch_steam_library(st.session_state.steam_id)
    if library:
        st.write(f"Found {len(library)} games in your library:")
        for game in library:
            st.write(f"**{game['name']}** - {game['playtime_forever']} minutes played")
    else:
        st.write("It looks like your Steam library is private or no games were found. Please make your library public in your Steam settings.")
