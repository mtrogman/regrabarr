"""
Regrabarr - Discord bot for managing Sonarr/Radarr media re-downloads.
Enterprise-grade implementation with security hardening.
"""
import sys
import asyncio
import urllib.parse
from datetime import datetime
from typing import Optional, Dict, Any, List

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, View, Button
import yaml
import logging

# ============================================================================
# Constants
# ============================================================================
REQUEST_TIMEOUT = 30  # seconds
MAX_SEARCH_RESULTS = 10
MAX_INPUT_LENGTH = 200
VIEW_TIMEOUT = 300  # 5 minutes for UI interactions
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds
STARTUP_RETRY_DELAY = 30  # seconds between startup retries
STARTUP_MAX_RETRIES = 5  # max retries for initial service connection
BACKGROUND_RETRY_INTERVAL = 60  # seconds between background retry attempts

# ============================================================================
# Logging Configuration
# ============================================================================
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration Loading and Validation
# ============================================================================
def load_config(file_path: str) -> dict:
    """Load and validate configuration from YAML file."""
    try:
        with open(file_path, 'r') as yaml_file:
            config = yaml.safe_load(yaml_file)
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {file_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML in configuration file: {e}")
        sys.exit(1)

    # Validate required fields
    required_fields = [
        ('bot', 'token'),
        ('sonarr', 'api_key'),
        ('sonarr', 'url'),
        ('radarr', 'api_key'),
        ('radarr', 'url'),
    ]

    for section, field in required_fields:
        if section not in config:
            logger.error(f"Missing required config section: {section}")
            sys.exit(1)
        if field not in config[section]:
            logger.error(f"Missing required config field: {section}.{field}")
            sys.exit(1)
        if not config[section][field]:
            logger.error(f"Empty required config field: {section}.{field}")
            sys.exit(1)

    return config


# Load configuration
config_location = "/config/config.yml"
config = load_config(config_location)

# Extract configuration values
bot_token = config['bot']['token']
radarr_api_key = config['radarr']['api_key']
radarr_base_url = config['radarr']['url'].rstrip('/')
sonarr_api_key = config['sonarr']['api_key']
sonarr_base_url = config['sonarr']['url'].rstrip('/')

regrab_movie_command_name = config['bot'].get('regrab_movie', 'regrab_movie')
regrab_episode_command_name = config['bot'].get('regrab_episode', 'regrab_episode')

# Optional: Authorized roles (if not specified, all users can use commands)
authorized_roles = config['bot'].get('authorized_roles', [])

# ============================================================================
# Discord Bot Initialization (Minimal Intents)
# ============================================================================
intents = discord.Intents.default()
# Only enable intents we actually need
intents.guilds = True  # Required for slash commands
bot = commands.Bot(command_prefix="!", intents=intents)

# Global aiohttp session (initialized on bot ready)
http_session: Optional[aiohttp.ClientSession] = None

# Cached configuration values (populated on startup)
sonarr_root_folder_path: Optional[str] = None
radarr_root_folder_path: Optional[str] = None
sonarr_quality_profile_id: Optional[int] = None
radarr_quality_profile_id: Optional[int] = None

# Service availability tracking
sonarr_available: bool = False
radarr_available: bool = False
config_retry_task: Optional[asyncio.Task] = None


# ============================================================================
# Input Validation
# ============================================================================
def sanitize_input(user_input: str) -> str:
    """Sanitize and validate user input."""
    if not user_input:
        return ""
    # Strip whitespace and limit length
    sanitized = user_input.strip()[:MAX_INPUT_LENGTH]
    # URL encode for safe use in API calls
    return urllib.parse.quote(sanitized, safe='')


def validate_input(user_input: str) -> tuple[bool, str]:
    """Validate user input and return (is_valid, sanitized_input or error_message)."""
    if not user_input or not user_input.strip():
        return False, "Search term cannot be empty"
    if len(user_input) > MAX_INPUT_LENGTH:
        return False, f"Search term too long (max {MAX_INPUT_LENGTH} characters)"
    return True, user_input.strip()


# ============================================================================
# Authorization Check
# ============================================================================
def check_authorization(interaction: discord.Interaction) -> bool:
    """Check if user is authorized to use regrab commands."""
    # If no roles configured, allow all users
    if not authorized_roles:
        return True

    # Check if user has any of the authorized roles
    if interaction.guild is None:
        return False

    member = interaction.guild.get_member(interaction.user.id)
    if member is None:
        return False

    user_role_names = [role.name.lower() for role in member.roles]
    for auth_role in authorized_roles:
        if auth_role.lower() in user_role_names:
            return True

    return False


# ============================================================================
# Async HTTP Client with Retry Logic
# ============================================================================
async def perform_request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    timeout: int = REQUEST_TIMEOUT
) -> Optional[aiohttp.ClientResponse]:
    """
    Perform an async HTTP request with retry logic and proper error handling.
    API keys are passed via headers, never in URLs.
    """
    global http_session

    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession()

    for attempt in range(MAX_RETRIES):
        try:
            timeout_config = aiohttp.ClientTimeout(total=timeout)

            async with http_session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                timeout=timeout_config
            ) as response:
                # Read the response body while in context
                response_data = await response.read()
                # Create a simple response object to return
                return ResponseWrapper(
                    status_code=response.status,
                    data=response_data,
                    headers=dict(response.headers)
                )

        except aiohttp.ClientError as e:
            logger.warning(f"Request attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))  # Exponential backoff
            else:
                logger.error(f"All {MAX_RETRIES} request attempts failed for {url}: {e}")
                return None

        except asyncio.TimeoutError:
            logger.warning(f"Request timeout (attempt {attempt + 1}/{MAX_RETRIES}) for {url}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
            else:
                logger.error(f"Request timed out after {MAX_RETRIES} attempts: {url}")
                return None

    return None


class ResponseWrapper:
    """Simple wrapper to hold response data after the context manager closes."""
    def __init__(self, status_code: int, data: bytes, headers: dict):
        self.status_code = status_code
        self._data = data
        self.headers = headers

    def json(self) -> Any:
        import json
        return json.loads(self._data.decode('utf-8'))

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400


# ============================================================================
# API Helper Functions (Headers-based Authentication)
# ============================================================================
def get_sonarr_headers() -> Dict[str, str]:
    """Get headers for Sonarr API requests."""
    return {
        "X-Api-Key": sonarr_api_key,
        "Content-Type": "application/json"
    }


def get_radarr_headers() -> Dict[str, str]:
    """Get headers for Radarr API requests."""
    return {
        "X-Api-Key": radarr_api_key,
        "Content-Type": "application/json"
    }


async def get_quality_profiles(base_url: str, headers: Dict[str, str]) -> List[dict]:
    """Fetch quality profiles from Sonarr/Radarr."""
    url = f"{base_url}/qualityprofile"
    response = await perform_request('GET', url, headers=headers)

    if response and response.ok:
        return response.json()

    logger.error(f"Failed to get quality profiles from {base_url}")
    return []


async def get_root_folders(base_url: str, headers: Dict[str, str]) -> List[dict]:
    """Fetch root folders from Sonarr/Radarr."""
    url = f"{base_url}/rootfolder"
    response = await perform_request('GET', url, headers=headers)

    if response and response.ok:
        return response.json()

    logger.error(f"Failed to get root folders from {base_url}")
    return []


def select_root_folder(root_folders: List[dict]) -> str:
    """Select the first available root folder path."""
    if not root_folders:
        raise ValueError("No root folders available")
    return root_folders[0]['path']


def select_quality_profile(profiles: List[dict]) -> int:
    """Select the first available quality profile ID."""
    if not profiles:
        raise ValueError("No quality profiles available")
    return profiles[0]['id']


# ============================================================================
# Media Fetch Functions
# ============================================================================
async def fetch_movie(movie_name: str) -> List[dict]:
    """Fetch movie search results from Radarr."""
    # Input is already validated by command handler
    url = f"{radarr_base_url}/movie/lookup"
    params = {"term": movie_name}
    headers = get_radarr_headers()

    response = await perform_request('GET', url, headers=headers, params=params)

    if response and response.ok:
        movie_list = response.json()
        return movie_list[:MAX_SEARCH_RESULTS]

    logger.error(f"Failed to fetch movie data for: {movie_name}")
    return []


async def fetch_series(series_name: str) -> List[dict]:
    """Fetch series search results from Sonarr."""
    url = f"{sonarr_base_url}/series/lookup"
    params = {"term": series_name}
    headers = get_sonarr_headers()

    response = await perform_request('GET', url, headers=headers, params=params)

    if response and response.ok:
        series_list = response.json()
        return series_list[:MAX_SEARCH_RESULTS]

    logger.error(f"Failed to fetch series data for: {series_name}")
    return []


def get_seasons(series_data: dict) -> List[dict]:
    """Extract seasons from series data, excluding specials (season 0)."""
    seasons = series_data.get('seasons', [])
    return [season for season in seasons if season['seasonNumber'] != 0]


async def fetch_episodes(series_id: int, season_number: int) -> List[dict]:
    """Fetch episodes for a specific series and season."""
    url = f"{sonarr_base_url}/episode"
    params = {
        'seriesId': series_id,
        'seasonNumber': season_number
    }
    headers = get_sonarr_headers()

    logger.info(f"Fetching episodes for series {series_id}, season {season_number}")
    response = await perform_request('GET', url, headers=headers, params=params)

    if response and response.ok:
        return response.json()

    logger.warning(f"Failed to fetch episodes for series {series_id}, season {season_number}")
    return []


def extract_episode_details(episode_data: dict) -> dict:
    """Extract relevant details from episode data."""
    return {
        'title': episode_data.get('title', 'Unknown'),
        'episodeNumber': episode_data.get('episodeNumber', 0),
        'overview': episode_data.get('overview', 'No overview available'),
        'episodeFileId': episode_data.get('episodeFileId', 0),
        'episodeId': episode_data.get('id', 0),
        'airDate': episode_data.get('airDate', 'Unknown'),
    }


# ============================================================================
# Regrab Operations
# ============================================================================
async def regrab_movie_action(media_info: dict) -> tuple[bool, str]:
    """
    Execute the movie regrab action.
    Returns (success, message).
    """
    movie_title = media_info['title']
    movie_year = media_info['year']
    movie_id = media_info['movieId']
    movie_tmdb = media_info['tmdbId']

    headers = get_radarr_headers()

    # Step 1: Delete the movie
    delete_url = f"{radarr_base_url}/movie/{movie_id}"
    params = {"deleteFiles": "true"}

    delete_response = await perform_request('DELETE', delete_url, headers=headers, params=params)

    if delete_response:
        logger.info(f"Deleted movie '{movie_title}' (ID: {movie_id}), status: {delete_response.status_code}")
    else:
        logger.warning(f"Delete request failed for movie '{movie_title}', continuing with add...")

    # Step 2: Re-add the movie with search enabled
    add_url = f"{radarr_base_url}/movie"
    add_data = {
        "tmdbId": movie_tmdb,
        "title": movie_title,
        "year": movie_year,
        "qualityProfileId": radarr_quality_profile_id,
        "rootFolderPath": radarr_root_folder_path,
        "monitored": True,
        "minimumAvailability": "released",
        "addOptions": {
            "searchForMovie": True
        }
    }

    add_response = await perform_request('POST', add_url, headers=headers, json_data=add_data)

    if add_response and add_response.ok:
        logger.info(f"Added movie '{movie_title}' for download")
        return True, f"Your request to delete and redownload {movie_title} ({movie_year}) is being processed."
    else:
        status = add_response.status_code if add_response else "No response"
        logger.error(f"Failed to add movie '{movie_title}', status: {status}")
        return False, f"Your request for {movie_title} ({movie_year}) had an issue, please contact the admin."


async def regrab_episode_action(media_info: dict) -> tuple[bool, str]:
    """
    Execute the episode regrab action.
    Returns (success, message).
    """
    series_name = media_info['series']
    season_num = media_info['seasonNumber']
    episode_num = media_info['episodeNumber']
    episode_file_id = media_info['episodeFileId']
    episode_id = media_info['episodeId']

    headers = get_sonarr_headers()

    # Step 1: Delete episode file if it exists
    if episode_file_id and episode_file_id != 0:
        delete_url = f"{sonarr_base_url}/episodefile/{episode_file_id}"
        delete_response = await perform_request('DELETE', delete_url, headers=headers)

        if delete_response:
            logger.info(f"Deleted episode file {episode_file_id}, status: {delete_response.status_code}")
        else:
            logger.warning(f"Failed to delete episode file {episode_file_id}")
    else:
        logger.info(f"No existing episode file to delete for {series_name} S{season_num}E{episode_num}")

    # Step 2: Trigger episode search
    search_url = f"{sonarr_base_url}/command"
    search_data = {
        "episodeIds": [episode_id],
        "name": "EpisodeSearch",
    }

    search_response = await perform_request('POST', search_url, headers=headers, json_data=search_data)

    if search_response and search_response.ok:
        logger.info(f"Triggered search for {series_name} S{season_num}E{episode_num}")
        return True, f"Your request to (re)grab {series_name} Season {season_num} Episode {episode_num} is being processed."
    else:
        status = search_response.status_code if search_response else "No response"
        logger.error(f"Failed to trigger search for episode, status: {status}")
        return False, f"Your request to (re)grab {series_name} Season {season_num} Episode {episode_num} had an issue, please contact the admin."


# ============================================================================
# Discord UI Components (Per-Interaction State)
# ============================================================================
class ConfirmButtonsMovie(View):
    """Confirmation buttons for movie regrab with per-interaction state."""

    def __init__(self, interaction: discord.Interaction, media_info: dict):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.original_interaction = interaction
        self.media_info = media_info.copy()  # Copy to ensure isolation

        regrab_button = Button(style=discord.ButtonStyle.primary, label="Regrab")
        regrab_button.callback = self.regrab_callback
        self.add_item(regrab_button)

        cancel_button = Button(style=discord.ButtonStyle.danger, label="Cancel")
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)

    async def regrab_callback(self, interaction: discord.Interaction):
        await self.original_interaction.delete_original_response()

        success, message = await regrab_movie_action(self.media_info)
        await self.original_interaction.followup.send(
            content=f"`{self.original_interaction.user.name}` {message}"
        )

    async def cancel_callback(self, interaction: discord.Interaction):
        await self.original_interaction.delete_original_response()
        await self.original_interaction.followup.send(
            content="Cancelled the request.",
            ephemeral=True
        )

    async def on_timeout(self):
        """Handle view timeout."""
        try:
            await self.original_interaction.delete_original_response()
        except discord.NotFound:
            pass  # Message already deleted


class ConfirmButtonsSeries(View):
    """Confirmation buttons for episode regrab with per-interaction state."""

    def __init__(self, interaction: discord.Interaction, media_info: dict):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.original_interaction = interaction
        self.media_info = media_info.copy()  # Copy to ensure isolation

        regrab_button = Button(style=discord.ButtonStyle.primary, label="Regrab")
        regrab_button.callback = self.regrab_callback
        self.add_item(regrab_button)

        cancel_button = Button(style=discord.ButtonStyle.danger, label="Cancel")
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)

    async def regrab_callback(self, interaction: discord.Interaction):
        await self.original_interaction.delete_original_response()

        success, message = await regrab_episode_action(self.media_info)
        await self.original_interaction.followup.send(
            content=f"`{self.original_interaction.user.name}` {message}"
        )

    async def cancel_callback(self, interaction: discord.Interaction):
        await self.original_interaction.delete_original_response()
        await self.original_interaction.followup.send(
            content="Cancelled the request.",
            ephemeral=True
        )

    async def on_timeout(self):
        """Handle view timeout."""
        try:
            await self.original_interaction.delete_original_response()
        except discord.NotFound:
            pass


class MovieSelectorView(View):
    """Movie selection dropdown with per-interaction state."""

    def __init__(self, search_results: List[dict], media_info: dict):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.search_results = search_results
        self.media_info = media_info
        self.add_item(MovieSelector(search_results, media_info))


class MovieSelector(Select):
    """Dropdown for selecting a movie."""

    def __init__(self, search_results: List[dict], media_info: dict):
        self.search_results = search_results
        self.media_info = media_info

        options = []
        for idx, movie in enumerate(search_results[:25]):  # Discord limit: 25 options
            # Truncate title if too long for Discord
            title = movie.get('title', 'Unknown')[:100]
            year = str(movie.get('year', 'Unknown'))[:100]
            options.append(discord.SelectOption(
                label=title,
                value=str(idx),
                description=year
            ))

        super().__init__(
            placeholder="Please select a movie",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        selected_index = int(self.values[0])
        selected_movie = self.search_results[selected_index]

        # Update media_info with selected movie data
        self.media_info['movieId'] = selected_movie.get('id', 0)
        self.media_info['tmdbId'] = selected_movie.get('tmdbId', 0)
        self.media_info['title'] = selected_movie.get('title', 'Unknown Title')
        self.media_info['year'] = selected_movie.get('year', 'Unknown Year')
        self.media_info['overview'] = selected_movie.get('overview', 'No overview available')[:1000]

        confirmation_message = (
            f"Please confirm that you would like to regrab the following movie:\n"
            f"**Title:** {self.media_info['title']}\n"
            f"**Year:** {self.media_info['year']}\n"
            f"**Overview:** {self.media_info['overview']}\n"
        )

        confirmation_view = ConfirmButtonsMovie(interaction, self.media_info)
        await interaction.response.edit_message(content=confirmation_message, view=confirmation_view)


class SeriesSelectorView(View):
    """Series selection dropdown with per-interaction state."""

    def __init__(self, series_results: List[dict], media_info: dict):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.series_results = series_results
        self.media_info = media_info
        self.add_item(TVSeriesSelector(series_results, media_info))


class TVSeriesSelector(Select):
    """Dropdown for selecting a TV series."""

    def __init__(self, series_results: List[dict], media_info: dict):
        self.series_results = series_results
        self.media_info = media_info

        options = []
        for idx, series in enumerate(series_results[:25]):
            title = series.get('title', 'Unknown')[:100]
            year = str(series.get('year', 'Unknown'))[:100]
            options.append(discord.SelectOption(
                label=title,
                value=str(idx),
                description=year
            ))

        super().__init__(
            placeholder="Please select a TV series",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        selected_index = int(self.values[0])
        selected_series = self.series_results[selected_index]

        self.media_info['series'] = selected_series.get('title', 'Unknown')
        self.media_info['seriesId'] = selected_series.get('id', 0)

        seasons = get_seasons(selected_series)

        if not seasons:
            await interaction.response.edit_message(
                content="No seasons found for this series.",
                view=None
            )
            return

        await interaction.response.edit_message(
            content="Please select a season",
            view=SeasonSelectorView(seasons, self.media_info)
        )


class SeasonSelectorView(View):
    """Season selection dropdown with per-interaction state."""

    def __init__(self, season_results: List[dict], media_info: dict):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.season_results = season_results
        self.media_info = media_info
        self.add_item(SeasonSelector(season_results, media_info))


class SeasonSelector(Select):
    """Dropdown for selecting a season."""

    def __init__(self, seasons_results: List[dict], media_info: dict):
        self.seasons_results = seasons_results
        self.media_info = media_info

        options = []
        for idx, season in enumerate(seasons_results[:25]):
            season_num = season.get('seasonNumber', 0)
            options.append(discord.SelectOption(
                label=f"Season {season_num}",
                value=str(idx)
            ))

        super().__init__(
            placeholder="Please select a season",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        selected_index = int(self.values[0])
        selected_season = self.seasons_results[selected_index]

        self.media_info['seasonNumber'] = selected_season.get('seasonNumber', 0)

        episodes = await fetch_episodes(
            self.media_info['seriesId'],
            self.media_info['seasonNumber']
        )

        if not episodes:
            await interaction.response.edit_message(
                content="No episodes found for this season.",
                view=None
            )
            return

        await interaction.response.edit_message(
            content="Please select an episode",
            view=EpisodeSelectorView(episodes, self.media_info)
        )


class EpisodeSelectorView(View):
    """Episode selection dropdown with per-interaction state."""

    def __init__(self, episode_results: List[dict], media_info: dict):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.episode_results = episode_results
        self.media_info = media_info
        self.add_item(EpisodeSelector(episode_results, media_info))


class EpisodeSelector(Select):
    """Dropdown for selecting an episode (only shows aired episodes)."""

    def __init__(self, episodes_results: List[dict], media_info: dict):
        self.episodes_results = episodes_results
        self.media_info = media_info
        self.episode_index_map = {}  # Maps option value to actual episode index

        current_date = datetime.now().date()
        options = []
        option_idx = 0

        for idx, episode in enumerate(episodes_results):
            episode_number = episode.get('episodeNumber', 0)
            air_date_str = episode.get('airDate', '')

            # Check if episode has aired
            try:
                air_date = datetime.strptime(air_date_str, "%Y-%m-%d").date()
                is_aired = air_date <= current_date
            except (ValueError, TypeError):
                is_aired = False

            if is_aired and option_idx < 25:  # Discord limit
                formatted_date = air_date.strftime('%b %d %Y') if air_date_str else 'Unknown'
                options.append(discord.SelectOption(
                    label=f"Episode {episode_number}",
                    value=str(option_idx),
                    description=f"Air Date: {formatted_date}"
                ))
                self.episode_index_map[str(option_idx)] = idx
                option_idx += 1

        if not options:
            # Fallback if no aired episodes
            options.append(discord.SelectOption(
                label="No aired episodes",
                value="none",
                description="No episodes available"
            ))

        super().__init__(
            placeholder="Please select an episode",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.edit_message(
                content="No aired episodes available for selection.",
                view=None
            )
            return

        actual_index = self.episode_index_map.get(self.values[0], 0)
        episode_data = self.episodes_results[actual_index]

        # Extract episode details into media_info
        details = extract_episode_details(episode_data)
        self.media_info.update(details)

        confirmation_message = (
            f"Please confirm that you would like to regrab the following episode:\n"
            f"**Series:** {self.media_info['series']}\n"
            f"**Season:** Season {self.media_info['seasonNumber']}\n"
            f"**Episode:** Episode {self.media_info['episodeNumber']}\n"
            f"**Title:** {self.media_info['title']}\n"
            f"**Air Date:** {self.media_info['airDate']}\n"
            f"**Overview:** {self.media_info['overview'][:500]}\n"
        )

        confirmation_view = ConfirmButtonsSeries(interaction, self.media_info)
        await interaction.response.edit_message(content=confirmation_message, view=confirmation_view)


# ============================================================================
# Service Configuration Functions
# ============================================================================
async def initialize_sonarr_config() -> bool:
    """
    Initialize Sonarr configuration.
    Returns True if successful, False otherwise.
    """
    global sonarr_root_folder_path, sonarr_quality_profile_id, sonarr_available

    try:
        sonarr_headers = get_sonarr_headers()
        sonarr_root_folders = await get_root_folders(sonarr_base_url, sonarr_headers)
        sonarr_quality_profiles = await get_quality_profiles(sonarr_base_url, sonarr_headers)

        if not sonarr_root_folders:
            logger.warning("Sonarr: No root folders available")
            return False

        if not sonarr_quality_profiles:
            logger.warning("Sonarr: No quality profiles available")
            return False

        sonarr_root_folder_path = sonarr_root_folders[0]['path']
        sonarr_quality_profile_id = sonarr_quality_profiles[0]['id']
        sonarr_available = True

        logger.info(f"Sonarr connected - Root Folder: {sonarr_root_folder_path}, Quality Profile ID: {sonarr_quality_profile_id}")
        return True

    except Exception as e:
        logger.warning(f"Sonarr initialization failed: {e}")
        sonarr_available = False
        return False


async def initialize_radarr_config() -> bool:
    """
    Initialize Radarr configuration.
    Returns True if successful, False otherwise.
    """
    global radarr_root_folder_path, radarr_quality_profile_id, radarr_available

    try:
        radarr_headers = get_radarr_headers()
        radarr_root_folders = await get_root_folders(radarr_base_url, radarr_headers)
        radarr_quality_profiles = await get_quality_profiles(radarr_base_url, radarr_headers)

        if not radarr_root_folders:
            logger.warning("Radarr: No root folders available")
            return False

        if not radarr_quality_profiles:
            logger.warning("Radarr: No quality profiles available")
            return False

        radarr_root_folder_path = radarr_root_folders[0]['path']
        radarr_quality_profile_id = radarr_quality_profiles[0]['id']
        radarr_available = True

        logger.info(f"Radarr connected - Root Folder: {radarr_root_folder_path}, Quality Profile ID: {radarr_quality_profile_id}")
        return True

    except Exception as e:
        logger.warning(f"Radarr initialization failed: {e}")
        radarr_available = False
        return False


async def retry_unavailable_services():
    """
    Background task to retry connecting to unavailable services.
    Runs periodically until all services are available.
    """
    global sonarr_available, radarr_available

    while True:
        await asyncio.sleep(BACKGROUND_RETRY_INTERVAL)

        # Check if all services are available
        if sonarr_available and radarr_available:
            logger.info("All services available, stopping retry task")
            break

        # Retry unavailable services
        if not sonarr_available:
            logger.info("Retrying Sonarr connection...")
            await initialize_sonarr_config()

        if not radarr_available:
            logger.info("Retrying Radarr connection...")
            await initialize_radarr_config()


# ============================================================================
# Bot Events
# ============================================================================
@bot.event
async def on_ready():
    """Initialize bot and fetch configuration from Sonarr/Radarr."""
    global http_session, config_retry_task

    logger.info('Bot is starting up...')

    # Initialize HTTP session if not already done
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession()

    # Try to initialize services (don't crash if they fail)
    sonarr_ok = await initialize_sonarr_config()
    radarr_ok = await initialize_radarr_config()

    # Log status
    if sonarr_ok and radarr_ok:
        logger.info("All services initialized successfully")
    else:
        services_down = []
        if not sonarr_ok:
            services_down.append("Sonarr")
        if not radarr_ok:
            services_down.append("Radarr")
        logger.warning(f"Some services unavailable: {', '.join(services_down)}. Commands for these services will be disabled until they reconnect.")

        # Start background retry task if not already running
        if config_retry_task is None or config_retry_task.done():
            config_retry_task = asyncio.create_task(retry_unavailable_services())
            logger.info("Started background service retry task")

    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")

    logger.info('Bot is Up and Ready!')


@bot.event
async def on_close():
    """Clean up resources when bot shuts down."""
    global http_session, config_retry_task

    # Cancel retry task if running
    if config_retry_task and not config_retry_task.done():
        config_retry_task.cancel()
        try:
            await config_retry_task
        except asyncio.CancelledError:
            pass
        logger.info("Background retry task cancelled")

    # Close HTTP session
    if http_session and not http_session.closed:
        await http_session.close()
        logger.info("HTTP session closed")


# ============================================================================
# Slash Commands with Rate Limiting
# ============================================================================
@bot.tree.command(name=regrab_movie_command_name, description="Will delete and redownload selected movie")
@app_commands.describe(movie="What movie should we regrab?")
@app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)  # 1 use per 30 seconds per user
async def regrab_movie(interaction: discord.Interaction, *, movie: str):
    """Command to regrab a movie."""
    # Service availability check
    if not radarr_available:
        await interaction.response.send_message(
            "Radarr is currently unavailable. Please try again later.",
            ephemeral=True
        )
        return

    # Authorization check
    if not check_authorization(interaction):
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    # Input validation
    is_valid, result = validate_input(movie)
    if not is_valid:
        await interaction.response.send_message(result, ephemeral=True)
        return

    # Fetch movies
    movie_results = await fetch_movie(result)

    if not movie_results:
        await interaction.response.send_message(
            f"{interaction.user.name}, no movie matching the following title was found: {movie}",
            ephemeral=True
        )
        return

    # Create fresh media_info for this interaction (CRITICAL: per-interaction state)
    media_info = {
        'what': 'movie',
        'delete': 'yes',
        'user_id': interaction.user.id,
        'user_name': interaction.user.name,
    }

    await interaction.response.send_message(
        "Select a movie to regrab",
        view=MovieSelectorView(movie_results, media_info),
        ephemeral=True
    )


@bot.tree.command(name=regrab_episode_command_name, description="Will delete and redownload selected episode")
@app_commands.describe(series="What TV series should we regrab from?")
@app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)  # 1 use per 30 seconds per user
async def regrab_episode(interaction: discord.Interaction, *, series: str):
    """Command to regrab a TV episode."""
    # Service availability check
    if not sonarr_available:
        await interaction.response.send_message(
            "Sonarr is currently unavailable. Please try again later.",
            ephemeral=True
        )
        return

    # Authorization check
    if not check_authorization(interaction):
        await interaction.response.send_message(
            "You do not have permission to use this command.",
            ephemeral=True
        )
        return

    # Input validation
    is_valid, result = validate_input(series)
    if not is_valid:
        await interaction.response.send_message(result, ephemeral=True)
        return

    # Fetch series
    series_results = await fetch_series(result)

    if not series_results:
        await interaction.response.send_message(
            f"No TV series matching the title: {series}",
            ephemeral=True
        )
        return

    # Create fresh media_info for this interaction (CRITICAL: per-interaction state)
    media_info = {
        'what': 'series',
        'delete': 'yes',
        'user_id': interaction.user.id,
        'user_name': interaction.user.name,
    }

    await interaction.response.send_message(
        "Select a TV series to regrab",
        view=SeriesSelectorView(series_results, media_info),
        ephemeral=True
    )


# Error handler for cooldown
@regrab_movie.error
@regrab_episode.error
async def on_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Handle command errors."""
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            f"This command is on cooldown. Try again in {error.retry_after:.1f} seconds.",
            ephemeral=True
        )
    else:
        logger.error(f"Command error: {error}")
        await interaction.response.send_message(
            "An error occurred while processing your request.",
            ephemeral=True
        )


# ============================================================================
# Main Entry Point
# ============================================================================
if __name__ == "__main__":
    bot.run(bot_token)
