import sys
import time
import logging
import requests
import yaml
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, View, Button
from datetime import datetime

# ------------- Logging -------------
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ------------- Config I/O -------------
def get_config(file):
    with open(file, "r") as yaml_file:
        return yaml.safe_load(yaml_file)

def save_config(file, config):
    with open(file, "w") as yaml_file:
        yaml.safe_dump(config, yaml_file, sort_keys=False)  # keep human layout

def ensure_section(cfg, name):
    if name not in cfg or cfg[name] is None:
        cfg[name] = {}

def normalize_base_url(u: str) -> str:
    return (u or "").rstrip("/")

# ------------- Constants -------------
REQUEST_TIMEOUT = 15

# ------------- Load config (startup behavior unchanged) -------------
config_location = "/config/config.yml"
config = get_config(config_location)

ensure_section(config, "bot")
ensure_section(config, "radarr")
ensure_section(config, "sonarr")

bot_token = config["bot"]["token"]

radarr_api_key = config["radarr"]["api_key"]
radarr_base_url = normalize_base_url(config["radarr"]["url"])
sonarr_api_key = config["sonarr"]["api_key"]
sonarr_base_url = normalize_base_url(config["sonarr"]["url"])

regrab_movie_command_name = config["bot"].get("regrab_movie", "regrab_movie")
regrab_episode_command_name = config["bot"].get("regrab_episode", "regrab_episode")

# ------------- HTTP session -------------
session = requests.Session()

def perform_request(method, url, data=None, headers=None, params=None):
    try:
        if method == "GET":
            response = session.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        elif method == "POST":
            response = session.post(url, json=data, headers=headers, timeout=REQUEST_TIMEOUT)
        elif method == "DELETE":
            response = session.delete(url, headers=headers, timeout=REQUEST_TIMEOUT)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        response.raise_for_status()
        return response
    except Exception as e:
        logging.error(f"{method} request failed: {e}")
        return None

# ------------- Discovery (unchanged startup methodology) -------------
def get_root_folders(base_url, api_key):
    url = f"{base_url}/rootfolder?apikey={api_key}"
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logging.error(f"Failed to get root folders from {base_url}: {e}")
        return []

def select_root_folder(folders):
    if folders:
        return folders[0]["path"]
    raise Exception("No root folders available")

def get_first_quality_profile(base_url, api_key):
    url = f"{base_url}/qualityprofile?apikey={api_key}"
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        profiles = resp.json()
        if profiles:
            return profiles[0]["id"]
        else:
            raise Exception("No quality profiles available")
    except Exception as e:
        logging.error(f"Failed to get quality profiles from {base_url}: {e}")
        return None

def ensure_config_value(section, key, fetch_func):
    if key not in config[section] or not config[section][key]:
        value = fetch_func()
        if value:
            config[section][key] = value
            save_config(config_location, config)
            logging.info(f"Set {key} for {section}: {value}")
        else:
            logging.critical(f"Could not fetch {key} for {section}. Exiting.")
            sys.exit(1)
    return config[section][key]

# Fill when missing
sonarr_quality_profile_id = ensure_config_value("sonarr", "qualityprofileid",
    lambda: get_first_quality_profile(sonarr_base_url, sonarr_api_key))
sonarr_root_folder_path = ensure_config_value("sonarr", "root_path",
    lambda: select_root_folder(get_root_folders(sonarr_base_url, sonarr_api_key)))

radarr_quality_profile_id = ensure_config_value("radarr", "qualityprofileid",
    lambda: get_first_quality_profile(radarr_base_url, radarr_api_key))
radarr_root_folder_path = ensure_config_value("radarr", "root_path",
    lambda: select_root_folder(get_root_folders(radarr_base_url, radarr_api_key)))

# ------------- Discord bot -------------
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

async def safe_delete_original(interaction: discord.Interaction):
    try:
        await interaction.delete_original_response()
    except Exception:
        pass

@bot.event
async def on_ready():
    logging.info("Bot is Up and Ready!")
    try:
        synced = await bot.tree.sync()
        logging.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logging.error(f"{e}")

# ------------- Radarr helpers -------------
def radarr_lookup(term: str):
    url = f"{radarr_base_url}/movie/lookup?term={term}"
    headers = {"X-Api-Key": radarr_api_key}
    return perform_request("GET", url, headers=headers)

def radarr_find_by_tmdb(tmdb_id: int):
    try:
        resp = session.get(
            f"{radarr_base_url}/movie",
            params={"tmdbId": tmdb_id},
            headers={"X-Api-Key": radarr_api_key},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.ok:
            data = resp.json()
            if isinstance(data, list) and data:
                return data[0]
    except Exception as e:
        logging.error(f"radarr_find_by_tmdb failed: {e}")
    return None

def radarr_add_and_search(tmdb_id: int, title: str, year, title_slug: str, images):
    payload = {
        "tmdbId": tmdb_id,
        "title": title,
        "year": year,
        "qualityProfileId": radarr_quality_profile_id,
        "titleSlug": title_slug or "",
        "images": images or [],
        "monitored": True,
        "rootFolderPath": radarr_root_folder_path,
        "addOptions": {"searchForMovie": True},
    }
    return perform_request("POST", f"{radarr_base_url}/movie?apikey={radarr_api_key}",
                           data=payload, headers={"Content-Type": "application/json"})

def radarr_delete_movie(movie_id: int, delete_files=True):
    return perform_request("DELETE",
        f"{radarr_base_url}/movie/{movie_id}?deleteFiles={'true' if delete_files else 'false'}&apikey={radarr_api_key}"
    )

def radarr_movies_search(movie_id: int):
    payload = {"name": "MoviesSearch", "movieIds": [movie_id]}
    return perform_request("POST", f"{radarr_base_url}/command/",
                           data=payload, headers={"Content-Type": "application/json", "X-Api-Key": radarr_api_key})

# ------------- Sonarr helpers -------------
def sonarr_series_lookup(term: str):
    url = f"{sonarr_base_url}/series/lookup?term={term}"
    headers = {"X-Api-Key": sonarr_api_key}
    return perform_request("GET", url, headers=headers)

def sonarr_series_all():
    try:
        resp = session.get(f"{sonarr_base_url}/series?apikey={sonarr_api_key}", timeout=REQUEST_TIMEOUT)
        if resp.ok:
            return resp.json()
    except Exception as e:
        logging.error(f"sonarr_series_all failed: {e}")
    return []

def sonarr_find_series_by_tvdb(tvdb_id: int):
    for s in sonarr_series_all():
        if s.get("tvdbId") == tvdb_id:
            return s
    return None

def sonarr_add_series(title: str, tvdb_id: int, title_slug: str, images):
    payload = {
        "title": title,
        "tvdbId": tvdb_id,
        "qualityProfileId": sonarr_quality_profile_id,
        "titleSlug": title_slug or "",
        "images": images or [],
        "monitored": True,
        "rootFolderPath": sonarr_root_folder_path,
        "addOptions": {"searchForMissingEpisodes": True},
    }
    return perform_request("POST", f"{sonarr_base_url}/series?apikey={sonarr_api_key}",
                           data=payload, headers={"Content-Type": "application/json"})

def sonarr_fetch_episodes(series_id: int, season_number: int):
    url = f"{sonarr_base_url}/episode"
    params = {"seriesId": series_id, "seasonNumber": season_number}
    headers = {"X-Api-Key": sonarr_api_key}
    return perform_request("GET", url, headers=headers, params=params)

def sonarr_delete_episodefile(episode_file_id: int):
    return perform_request("DELETE", f"{sonarr_base_url}/episodefile/{episode_file_id}?apikey={sonarr_api_key}")

def sonarr_episode_search(episode_id: int):
    payload = {"name": "EpisodeSearch", "episodeIds": [episode_id]}
    return perform_request("POST", f"{sonarr_base_url}/command/",
                           data=payload, headers={"Content-Type": "application/json", "X-Api-Key": sonarr_api_key})

def sonarr_series_search(series_id: int):
    payload = {"name": "SeriesSearch", "seriesId": series_id}
    return perform_request("POST", f"{sonarr_base_url}/command/",
                           data=payload, headers={"Content-Type": "application/json", "X-Api-Key": sonarr_api_key})

# ------------- MOVIE REGRAB FLOW -------------
async def fetch_movie_list(movie_name):
    resp = radarr_lookup(movie_name)
    if resp and resp.status_code == 200:
        return resp.json()[:10]
    return []

class ConfirmButtonsMovie(View):
    def __init__(self, interaction, media_info):
        super().__init__()
        self.interaction = interaction
        self.media_info = media_info

        regrab_button = Button(style=discord.ButtonStyle.primary, label="Regrab")
        regrab_button.callback = self.regrab_callback
        self.add_item(regrab_button)

        cancel_button = Button(style=discord.ButtonStyle.danger, label="Cancel")
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)

    async def regrab_callback(self, interaction):
        # remove ephemeral UI
        await safe_delete_original(self.interaction)

        # public placeholder
        status_msg = await interaction.channel.send("🔎 Working on your movie re-grab…")

        movie_title = self.media_info["title"]
        movie_year = self.media_info.get("year")
        tmdb_id = int(self.media_info["tmdbId"])

        # Ensure we know whether it exists in Radarr
        existing = radarr_find_by_tmdb(tmdb_id)

        if existing and existing.get("id"):
            # Delete whole movie (and files), then re-add with search
            movie_id = int(existing["id"])
            del_resp = radarr_delete_movie(movie_id, delete_files=True)
            if not (del_resp and 200 <= del_resp.status_code < 400):
                await status_msg.edit(content=f"❌ **{interaction.user.display_name}** — couldn’t delete **{movie_title} ({movie_year or 'N/A'})** from Radarr.")
                return

            # Re-add and search
            add_resp = radarr_add_and_search(
                tmdb_id=tmdb_id,
                title=movie_title,
                year=movie_year,
                title_slug=existing.get("titleSlug", ""),
                images=existing.get("images", []),
            )
            if add_resp and 200 <= add_resp.status_code < 400:
                await status_msg.edit(content=f"🔎 **{interaction.user.display_name}** — re-grabbing **{movie_title} ({movie_year or 'N/A'})** (deleted & started search).")
            else:
                await status_msg.edit(content=f"❌ **{interaction.user.display_name}** — re-grab failed for **{movie_title} ({movie_year or 'N/A'})**.")
            return

        # Not in Radarr — just add + search
        add_resp = radarr_add_and_search(
            tmdb_id=tmdb_id,
            title=movie_title,
            year=movie_year,
            title_slug=self.media_info.get("titleSlug", ""),
            images=self.media_info.get("images", []),
        )
        if add_resp and 200 <= add_resp.status_code < 400:
            await status_msg.edit(content=f"🔎 **{interaction.user.display_name}** — requested **{movie_title} ({movie_year or 'N/A'})** and started search.")
        else:
            await status_msg.edit(content=f"❌ **{interaction.user.display_name}** — request for **{movie_title} ({movie_year or 'N/A'})** failed. Try again later.")

    async def cancel_callback(self, interaction):
        try:
            await self.interaction.followup.send(content="Cancelled the request.", ephemeral=True)
        except Exception:
            pass

class MovieSelector(Select):
    def __init__(self, results, media_info):
        self.results = results
        self.media_info = media_info
        options = [
            discord.SelectOption(label=m["title"], value=str(i), description=str(m.get("year", "")))
            for i, m in enumerate(results)
        ]
        super().__init__(placeholder="Please select a movie", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        idx = int(self.values[0])
        m = self.results[idx]
        # Fill media_info for confirm step
        self.media_info.update({
            "title": m.get("title", "Unknown Title"),
            "year": m.get("year"),
            "tmdbId": m.get("tmdbId"),
            "titleSlug": m.get("titleSlug", ""),
            "images": m.get("images", []),
        })

        overview = m.get("overview", "No overview available.")
        confirmation_message = (
            f"Please confirm you want to **regrab**:\n"
            f"**Title:** {self.media_info['title']}\n"
            f"**Year:** {self.media_info.get('year','N/A')}\n"
            f"**Overview:** {overview}\n"
        )
        await interaction.response.edit_message(content=confirmation_message, view=ConfirmButtonsMovie(interaction, self.media_info))

class MovieSelectorView(View):
    def __init__(self, results, media_info):
        super().__init__(timeout=180)
        self.add_item(MovieSelector(results, media_info))

# ------------- EPISODE REGRAB FLOW -------------
async def fetch_series_list(series_name):
    resp = sonarr_series_lookup(series_name)
    if resp and resp.status_code == 200:
        return resp.json()[:10]
    return []

async def fetch_seasons(selected_series_data):
    seasons = selected_series_data.get("seasons", [])
    return [s for s in seasons if s.get("seasonNumber") != 0]

def past_aired_episodes(episodes):
    out = []
    today = datetime.now().date()
    for ep in episodes:
        air_date_str = ep.get("airDate")
        if not air_date_str:
            continue
        try:
            air_date = datetime.strptime(air_date_str, "%Y-%m-%d").date()
            if air_date <= today:
                out.append(ep)
        except ValueError:
            # Skip if Sonarr gives a non-parseable date
            pass
    return out

class ConfirmButtonsSeries(View):
    def __init__(self, interaction, media_info):
        super().__init__()
        self.interaction = interaction
        self.media_info = media_info

        regrab_button = Button(style=discord.ButtonStyle.primary, label="Regrab")
        regrab_button.callback = self.regrab_callback
        self.add_item(regrab_button)

        cancel_button = Button(style=discord.ButtonStyle.danger, label="Cancel")
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)

    async def regrab_callback(self, interaction):
        # remove ephemeral UI
        await safe_delete_original(self.interaction)

        # public placeholder
        status_msg = await interaction.channel.send("🔎 Working on your episode re-grab…")

        episode_id = self.media_info["episodeId"]
        episode_file_id = self.media_info.get("episodeFileId", 0)

        # If a file exists, delete it first
        if episode_file_id:
            del_resp = sonarr_delete_episodefile(episode_file_id)
            if not (del_resp and 200 <= del_resp.status_code < 400):
                await status_msg.edit(content=f"❌ **{interaction.user.display_name}** — couldn’t delete the existing file for "
                                              f"{self.media_info['series']} S{self.media_info['seasonNumber']:02d}E{self.media_info['episodeNumber']:02d}.")
                return

        # Kick off EpisodeSearch
        search_resp = sonarr_episode_search(episode_id)
        if search_resp and 200 <= search_resp.status_code < 400:
            await status_msg.edit(content=f"🔎 **{interaction.user.display_name}** — re-grabbing "
                                          f"{self.media_info['series']} S{self.media_info['seasonNumber']:02d}E{self.media_info['episodeNumber']:02d}.")
        else:
            await status_msg.edit(content=f"❌ **{interaction.user.display_name}** — re-grab failed for "
                                          f"{self.media_info['series']} S{self.media_info['seasonNumber']:02d}E{self.media_info['episodeNumber']:02d}.")

    async def cancel_callback(self, interaction):
        try:
            await self.interaction.followup.send(content="Cancelled the request.", ephemeral=True)
        except Exception:
            pass

class TVSeriesSelector(Select):
    def __init__(self, series_results, media_info):
        self.series_results = series_results
        self.media_info = media_info
        options = [
            discord.SelectOption(label=s["title"], value=str(i), description=str(s.get("year", "")))
            for i, s in enumerate(series_results)
        ]
        super().__init__(placeholder="Please select a TV series", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        idx = int(self.values[0])
        selected = self.series_results[idx]

        # Ensure series exists in Sonarr; if not, add and then re-fetch to get its id
        if "id" not in selected:
            add_resp = sonarr_add_series(
                title=selected["title"],
                tvdb_id=selected["tvdbId"],
                title_slug=selected.get("titleSlug", ""),
                images=selected.get("images", []),
            )
            if not (add_resp and 200 <= add_resp.status_code < 400):
                try:
                    await interaction.response.edit_message(content="Failed to add series to Sonarr. Please try again.")
                except discord.errors.NotFound:
                    try:
                        await interaction.followup.send("This session has expired. Please re-run the command.", ephemeral=True)
                    except Exception:
                        pass
                return
            # replace with stored series having id
            for s in sonarr_series_all():
                if s.get("tvdbId") == selected["tvdbId"]:
                    selected = s
                    break

        self.media_info["series"] = selected["title"]
        self.media_info["seriesId"] = selected["id"]

        seasons = await fetch_seasons(selected)
        try:
            await interaction.response.edit_message(content="Please select a season", view=SeasonSelectorView(seasons, self.media_info))
        except discord.errors.NotFound:
            try:
                await interaction.followup.send("This session has expired. Please re-run the command.", ephemeral=True)
            except Exception:
                pass

class SeasonSelector(Select):
    def __init__(self, seasons_results, media_info):
        self.seasons_results = seasons_results
        self.media_info = media_info
        options = [
            discord.SelectOption(label=f"Season {s['seasonNumber']}", value=str(i))
            for i, s in enumerate(seasons_results)
        ]
        super().__init__(placeholder="Please select a season", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        idx = int(self.values[0])
        season_number = self.seasons_results[idx]["seasonNumber"]
        self.media_info["seasonNumber"] = season_number

        resp = sonarr_fetch_episodes(self.media_info["seriesId"], season_number)
        episodes = resp.json() if resp and resp.status_code == 200 else []
        episodes = past_aired_episodes(episodes)

        if not episodes:
            try:
                await interaction.response.edit_message(
                    content="No aired episodes available yet for this season. Try again later.",
                    view=None,
                )
            except discord.errors.NotFound:
                try:
                    await interaction.followup.send("This session has expired. Please re-run the command.", ephemeral=True)
                except Exception:
                    pass
            return

        try:
            await interaction.response.edit_message(content="Please select an episode", view=EpisodeSelectorView(episodes, self.media_info))
        except discord.errors.NotFound:
            try:
                await interaction.followup.send("This session has expired. Please re-run the command.", ephemeral=True)
            except Exception:
                pass

class EpisodeSelector(Select):
    def __init__(self, episodes_results, media_info):
        self.episodes_results = episodes_results
        self.media_info = media_info
        today = datetime.now().date()
        options = []
        for i, ep in enumerate(episodes_results):
            ep_no = ep.get("episodeNumber")
            air = ep.get("airDate")
            desc = None
            if air:
                try:
                    d = datetime.strptime(air, "%Y-%m-%d").date()
                    if d <= today:
                        desc = f"Air Date: {d.strftime('%b %d %Y')}"
                except ValueError:
                    pass
            options.append(discord.SelectOption(label=f"Episode {ep_no}", value=str(i), description=desc))
        super().__init__(placeholder="Please select an episode", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        idx = int(self.values[0])
        ep = self.episodes_results[idx]
        self.media_info.update({
            "episodeId": ep["id"],
            "episodeNumber": ep["episodeNumber"],
            "title": ep.get("title", ""),
            "overview": ep.get("overview", ""),
            "episodeFileId": ep.get("episodeFileId", 0),
        })
        content = (
            f"Please confirm you want to **regrab**:\n"
            f"**Series:** {self.media_info['series']}\n"
            f"**Season:** {self.media_info['seasonNumber']}\n"
            f"**Episode:** {self.media_info['episodeNumber']}\n"
            f"**Title:** {self.media_info.get('title', '')}\n"
            f"**Overview:** {self.media_info.get('overview', 'No overview')}\n"
        )
        await interaction.response.edit_message(content=content, view=ConfirmButtonsSeries(interaction, self.media_info))

class SeriesSelectorView(View):
    def __init__(self, series_results, media_info):
        super().__init__(timeout=180)
        self.add_item(TVSeriesSelector(series_results, media_info))

class SeasonSelectorView(View):
    def __init__(self, seasons_results, media_info):
        super().__init__(timeout=180)
        self.add_item(SeasonSelector(seasons_results, media_info))

class EpisodeSelectorView(View):
    def __init__(self, episodes_results, media_info):
        super().__init__(timeout=180)
        self.add_item(EpisodeSelector(episodes_results, media_info))

# ------------- Slash Commands (with “🔎 Searching…” window) -------------
@bot.tree.command(name=regrab_movie_command_name, description="Delete and redownload the selected movie")
@app_commands.describe(movie="What movie should we regrab?")
async def regrab_movie(ctx, *, movie: str):
    await ctx.response.defer(ephemeral=True)
    searching = await ctx.followup.send("🔎 Searching for movies…", ephemeral=True)
    results = await fetch_movie_list(movie)
    if not results:
        await searching.edit(content=f"No movie matching the title: {movie}")
        return
    media_info = {}
    await searching.edit(content="Select a movie to regrab:", view=MovieSelectorView(results, media_info))

@bot.tree.command(name=regrab_episode_command_name, description="Delete and redownload the selected episode")
@app_commands.describe(series="What TV series should we regrab from?")
async def regrab_episode(ctx, *, series: str):
    await ctx.response.defer(ephemeral=True)
    searching = await ctx.followup.send("🔎 Searching for shows…", ephemeral=True)
    series_results = await fetch_series_list(series)
    if not series_results:
        await searching.edit(content=f"No TV series matching the title: {series}")
        return
    media_info = {}
    await searching.edit(content="Select a TV series to regrab:", view=SeriesSelectorView(series_results, media_info))

if __name__ == "__main__":
    bot.run(bot_token)
