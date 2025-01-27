"""Tools for interacting with Spotify."""

import asyncio
import os
import httpx
import json
import base64
import webbrowser
import urllib.parse
from dotenv import load_dotenv
from http.server import BaseHTTPRequestHandler, HTTPServer
from src.utils.logging import get_logger

load_dotenv()

logger = get_logger(__name__)

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_API_BASE_URL = "https://api.spotify.com/v1"
REDIRECT_URI = "http://localhost:8888/callback"  # Must match the one in your Spotify app settings
TOKEN_STORE_FILE = "token_store.json"
SCOPES = "user-modify-playback-state user-read-playback-state user-library-modify user-library-read"  # Add more scopes as needed

class RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global AUTH_CODE
        parsed_url = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        if "code" in query_params:
            AUTH_CODE = query_params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"Authorization successful! You can close this window.")
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"Authorization failed.")

async def fetch_with_retry(url: str, headers: dict, params: dict, method: str = "GET", max_retries=3):
    """Fetches URL with retry logic."""
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                if method == "GET":
                    response = await client.get(url, headers=headers, params=params)
                elif method == "POST":
                    response = await client.post(url, headers=headers, data=params)
                elif method == "PUT":
                    response = await client.put(url, headers=headers, data=params)
                elif method == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    raise ValueError(f"Invalid method: {method}")
                response.raise_for_status()
                return response
        except httpx.HTTPError as e:
            if attempt == max_retries - 1:
                logger.error(f"Request failed after multiple retries: {e}")
                raise
            logger.warning(f"Error during fetch: {e}. Retrying in 2 seconds...")
            await asyncio.sleep(2)
    return None

def generate_spotify_auth_url():
    """Generates the Spotify authorization URL."""
    params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
    }
    return f"{SPOTIFY_AUTH_URL}?{urllib.parse.urlencode(params)}"

def run_local_server():
    """Runs a local server to handle the redirect URI."""
    server_address = ("", 8888)
    httpd = HTTPServer(server_address, RedirectHandler)
    httpd.handle_request()

async def exchange_code_for_token(auth_code: str):
    """Exchanges the authorization code for an access token."""
    auth_header = base64.b64encode(
        f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode("utf-8")
    ).decode("utf-8")

    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
    }

    response = await fetch_with_retry(SPOTIFY_TOKEN_URL, headers, data, method="POST")
    if response:
        return response.json()
    else:
        raise Exception("Failed to exchange authorization code for token.")

async def refresh_access_token(refresh_token: str):
    """Refreshes the access token."""
    auth_header = base64.b64encode(
        f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode("utf-8")
    ).decode("utf-8")

    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    response = await fetch_with_retry(SPOTIFY_TOKEN_URL, headers, data, method="POST")
    if response:
        token_data = response.json()
        token_data["refresh_token"] = refresh_token  # Keep the old refresh token
        return token_data
    else:
        raise Exception("Failed to refresh access token.")

def store_token_data(token_data):
    """Stores the token data to a JSON file."""
    with open(TOKEN_STORE_FILE, "w") as f:
        json.dump(token_data, f)

def load_token_data():
    """Loads the token data from a JSON file."""
    try:
        with open(TOKEN_STORE_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None

async def get_spotify_access_token():
    """Gets a Spotify access token, handling authorization and refresh."""
    global AUTH_CODE
    token_data = load_token_data()

    if token_data:
        if token_data["expires_at"] > asyncio.get_event_loop().time():
            return token_data["access_token"]
        else:
            try:
                token_data = await refresh_access_token(token_data["refresh_token"])
                token_data["expires_at"] = asyncio.get_event_loop().time() + token_data["expires_in"]
                store_token_data(token_data)
                return token_data["access_token"]
            except Exception as e:
                logger.error(f"Error refreshing token: {e}")
                # If refresh fails, re-authorize
                token_data = None

    if not token_data:
        auth_url = generate_spotify_auth_url()
        logger.info(f"Please go to this URL to authorize the application: {auth_url}")
        webbrowser.open(auth_url)
        run_local_server()  # Wait for the callback and get the auth code

        if AUTH_CODE:
            token_data = await exchange_code_for_token(AUTH_CODE)
            token_data["expires_at"] = asyncio.get_event_loop().time() + token_data["expires_in"]
            store_token_data(token_data)
            AUTH_CODE = None
            return token_data["access_token"]
        else:
            raise Exception("Authorization failed.")

async def spotify_play(access_token: str):
    """Starts or resumes Spotify playback."""
    url = f"{SPOTIFY_API_BASE_URL}/me/player/play"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = await fetch_with_retry(url, headers, {}, method="PUT")
    return response

async def spotify_pause(access_token: str):
    """Pauses Spotify playback."""
    url = f"{SPOTIFY_API_BASE_URL}/me/player/pause"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = await fetch_with_retry(url, headers, {}, method="PUT")
    return response

async def spotify_next(access_token: str):
    """Skips to the next track."""
    url = f"{SPOTIFY_API_BASE_URL}/me/player/next"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = await fetch_with_retry(url, headers, {}, method="POST")
    return response

async def spotify_previous(access_token: str):
    """Skips to the previous track."""
    url = f"{SPOTIFY_API_BASE_URL}/me/player/previous"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = await fetch_with_retry(url, headers, {}, method="POST")
    return response

async def spotify_like(access_token: str, track_id: str):
    """Likes (saves) a track."""
    url = f"{SPOTIFY_API_BASE_URL}/me/tracks?ids={track_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = await fetch_with_retry(url, headers, {}, method="PUT")
    return response

async def spotify_unlike(access_token: str, track_id: str):
    """Unlikes (removes) a track."""
    url = f"{SPOTIFY_API_BASE_URL}/me/tracks?ids={track_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = await fetch_with_retry(url, headers, {}, method="DELETE")
    return response

async def spotify_get_current_track_id(access_token: str) -> str:
    """Gets the ID of the currently playing track."""
    url = f"{SPOTIFY_API_BASE_URL}/me/player/currently-playing"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = await fetch_with_retry(url, headers, {}, method="GET")
    
    if response and response.status_code == 200:
        track_data = response.json()
        if track_data and track_data["item"] and track_data["item"]["id"]:
            return track_data["item"]["id"]
    return None

async def spotify_like_current_track(access_token: str):
    """Likes the currently playing track."""
    track_id = await spotify_get_current_track_id(access_token)
    if track_id:
        return await spotify_like(access_token, track_id)
    else:
        return json.dumps({"type": "error", "message": "Could not find current track to like."})

async def spotify_unlike_current_track(access_token: str):
    """Unlikes the currently playing track."""
    track_id = await spotify_get_current_track_id(access_token)
    if track_id:
        return await spotify_unlike(access_token, track_id)
    else:
        return json.dumps({"type": "error", "message": "Could not find current track to unlike."})

async def spotify_get_saved_tracks(access_token: str, limit: int = 20, offset: int = 0):
    """Gets the user's saved tracks (liked songs)."""
    url = f"{SPOTIFY_API_BASE_URL}/me/tracks?limit={limit}&offset={offset}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = await fetch_with_retry(url, headers, {}, method="GET")
    
    if response and response.status_code == 200:
        saved_tracks_data = response.json()
        saved_tracks = []
        for item in saved_tracks_data.get("items", []):
            track = item.get("track")
            if track:
                saved_tracks.append({
                    "id": track.get("id"),
                    "name": track.get("name"),
                    "artists": ", ".join([artist.get("name") for artist in track.get("artists", [])]),
                    "uri": track.get("uri")
                })
        return saved_tracks
    else:
        return None

async def spotify_play_saved_tracks(access_token: str):
    """Plays the user's saved tracks."""
    saved_tracks = await spotify_get_saved_tracks(access_token, limit=50)  # Get up to 50 saved tracks
    if saved_tracks:
        track_uris = [track["uri"] for track in saved_tracks]
        url = f"{SPOTIFY_API_BASE_URL}/me/player/play"
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {"uris": track_uris}
        response = await fetch_with_retry(url, headers, data, method="PUT")
        return response
    else:
        return json.dumps({"type": "error", "message": "Could not retrieve saved tracks."})

async def spotify_get_playlists(access_token: str, limit: int = 20, offset: int = 0):
    """Gets the user's playlists."""
    url = f"{SPOTIFY_API_BASE_URL}/me/playlists?limit={limit}&offset={offset}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = await fetch_with_retry(url, headers, {}, method="GET")
    
    if response and response.status_code == 200:
        playlists_data = response.json()
        playlists = []
        for item in playlists_data.get("items", []):
            playlists.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "description": item.get("description"),
                "uri": item.get("uri")
            })
        return playlists
    else:
        return None

async def spotify_get_playlist_tracks(access_token: str, playlist_id: str, limit: int = 50, offset: int = 0):
    """Gets tracks from a specific playlist."""
    url = f"{SPOTIFY_API_BASE_URL}/playlists/{playlist_id}/tracks?limit={limit}&offset={offset}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = await fetch_with_retry(url, headers, {}, method="GET")

    if response and response.status_code == 200:
        tracks_data = response.json()
        tracks = []
        for item in tracks_data.get("items", []):
            track = item.get("track")
            if track:
                tracks.append({
                    "id": track.get("id"),
                    "name": track.get("name"),
                    "artists": ", ".join([artist.get("name") for artist in track.get("artists", [])]),
                    "uri": track.get("uri")
                })
        return tracks
    else:
        return None

async def spotify_play_playlist(access_token: str, playlist_id: str):
    """Plays a specific playlist."""
    playlist_tracks = await spotify_get_playlist_tracks(access_token, playlist_id)
    if playlist_tracks:
        track_uris = [track["uri"] for track in playlist_tracks]
        url = f"{SPOTIFY_API_BASE_URL}/me/player/play"
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {"uris": track_uris}
        response = await fetch_with_retry(url, headers, data, method="PUT")
        return response
    else:
        return json.dumps({"type": "error", "message": "Could not retrieve playlist tracks."})

async def handle_spotify_action(action: str, track_id: str = None, playlist_id: str = None):
    """Handles Spotify actions based on the given action string."""
    access_token = await get_spotify_access_token()

    if action == "play":
        response = await spotify_play(access_token)
    elif action == "pause":
        response = await spotify_pause(access_token)
    elif action == "next":
        response = await spotify_next(access_token)
    elif action == "previous":
        response = await spotify_previous(access_token)
    elif action == "like" and track_id:
        response = await spotify_like(access_token, track_id)
    elif action == "unlike" and track_id:
        response = await spotify_unlike(access_token, track_id)
    elif action == "like_current":
        response = await spotify_like_current_track(access_token)
    elif action == "unlike_current":
        response = await spotify_unlike_current_track(access_token)
    elif action == "play_saved_tracks":
        response = await spotify_play_saved_tracks(access_token)
    elif action == "get_playlists":
        playlists = await spotify_get_playlists(access_token)
        if playlists:
            return json.dumps({"type": "success", "playlists": playlists})
        else:
            return json.dumps({"type": "error", "message": "Could not retrieve playlists."})
    elif action == "play_playlist" and playlist_id:
        response = await spotify_play_playlist(access_token, playlist_id)
    else:
        return json.dumps({"type": "error", "message": "Invalid Spotify action or missing required parameters."})

    if response and response.status_code == 200:
        return json.dumps({"type": "success", "message": f"Spotify action '{action}' executed successfully."})
    elif response:
        return json.dumps({"type": "error", "message": f"Error executing Spotify action '{action}'. Status code: {response.status_code}"})
    else:
        return json.dumps({"type": "error", "message": f"Error executing Spotify action '{action}'."})