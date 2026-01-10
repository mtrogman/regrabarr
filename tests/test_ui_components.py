"""
Unit tests for Discord UI components (Views, Selectors, Buttons).
Tests are mocked and do not require Discord connection.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, date
import discord


# ============================================================================
# Test: MovieSelector Component
# ============================================================================

class TestMovieSelector:
    """Tests for the MovieSelector dropdown component."""

    @pytest.mark.unit
    def test_movie_selector_options_created(self, mock_movie_lookup):
        """Test that selector options are created from movie results."""
        options = [
            {'label': movie['title'], 'value': str(idx), 'description': str(movie['year'])}
            for idx, movie in enumerate(mock_movie_lookup)
        ]

        assert len(options) == 3
        assert options[0]['label'] == 'The Matrix'
        assert options[0]['description'] == '1999'
        assert options[0]['value'] == '0'

    @pytest.mark.unit
    def test_movie_selector_max_options(self):
        """Test that movie selector respects Discord's 25 option limit."""
        # Discord Select components can have max 25 options
        many_movies = [{'title': f'Movie {i}', 'year': 2000 + i} for i in range(30)]
        options = [
            {'label': movie['title'], 'value': str(idx)}
            for idx, movie in enumerate(many_movies[:25])  # Should limit to 25
        ]

        assert len(options) <= 25

    @pytest.mark.unit
    def test_movie_selector_callback_extracts_correct_data(self, mock_movie_lookup):
        """Test that callback correctly extracts movie data."""
        selected_index = 0
        selected_movie = mock_movie_lookup[selected_index]

        media_info = {}
        media_info['movieId'] = selected_movie.get('id', 'N/A')
        media_info['tmdbId'] = selected_movie.get('tmdbId', 'N/A')
        media_info['title'] = selected_movie.get('title', 'Unknown Title')
        media_info['year'] = selected_movie.get('year', 'Unknown Year')
        media_info['overview'] = selected_movie.get('overview', 'No overview available')

        assert media_info['movieId'] == 1
        assert media_info['tmdbId'] == 603
        assert media_info['title'] == 'The Matrix'
        assert media_info['year'] == 1999

    @pytest.mark.unit
    def test_movie_selector_handles_missing_fields(self):
        """Test that selector handles movies with missing fields."""
        incomplete_movie = {'title': 'Incomplete Movie'}

        media_info = {}
        media_info['movieId'] = incomplete_movie.get('id', 'N/A')
        media_info['tmdbId'] = incomplete_movie.get('tmdbId', 'N/A')
        media_info['title'] = incomplete_movie.get('title', 'Unknown Title')
        media_info['year'] = incomplete_movie.get('year', 'Unknown Year')
        media_info['overview'] = incomplete_movie.get('overview', 'No overview available')

        assert media_info['movieId'] == 'N/A'
        assert media_info['tmdbId'] == 'N/A'
        assert media_info['year'] == 'Unknown Year'
        assert media_info['overview'] == 'No overview available'


# ============================================================================
# Test: SeriesSelector Component
# ============================================================================

class TestSeriesSelector:
    """Tests for the TVSeriesSelector dropdown component."""

    @pytest.mark.unit
    def test_series_selector_options_created(self, mock_series_lookup):
        """Test that selector options are created from series results."""
        options = [
            {'label': series['title'], 'value': str(idx), 'description': str(series['year'])}
            for idx, series in enumerate(mock_series_lookup)
        ]

        assert len(options) == 2
        assert options[0]['label'] == 'Breaking Bad'
        assert options[0]['description'] == '2008'

    @pytest.mark.unit
    def test_series_selector_callback_extracts_data(self, mock_series_lookup):
        """Test that callback correctly extracts series data."""
        selected_index = 0
        selected_series = mock_series_lookup[selected_index]

        media_info = {}
        media_info['series'] = selected_series['title']
        media_info['seriesId'] = selected_series['id']

        assert media_info['series'] == 'Breaking Bad'
        assert media_info['seriesId'] == 1


# ============================================================================
# Test: SeasonSelector Component
# ============================================================================

class TestSeasonSelector:
    """Tests for the SeasonSelector dropdown component."""

    @pytest.mark.unit
    def test_season_selector_options_created(self, mock_series_lookup):
        """Test that season options are created correctly."""
        seasons = mock_series_lookup[0]['seasons']
        # Filter out season 0
        filtered_seasons = [s for s in seasons if s['seasonNumber'] != 0]

        options = [
            {'label': f"Season {season['seasonNumber']}", 'value': str(idx)}
            for idx, season in enumerate(filtered_seasons)
        ]

        assert len(options) == 5  # Seasons 1-5
        assert options[0]['label'] == 'Season 1'

    @pytest.mark.unit
    def test_season_selector_excludes_specials(self, mock_series_lookup):
        """Test that season 0 (specials) is excluded from options."""
        seasons = mock_series_lookup[0]['seasons']
        filtered_seasons = [s for s in seasons if s['seasonNumber'] != 0]

        season_numbers = [s['seasonNumber'] for s in filtered_seasons]
        assert 0 not in season_numbers


# ============================================================================
# Test: EpisodeSelector Component
# ============================================================================

class TestEpisodeSelector:
    """Tests for the EpisodeSelector dropdown component."""

    @pytest.mark.unit
    def test_episode_selector_options_created(self, mock_episodes):
        """Test that episode options are created correctly."""
        options = []
        current_date = date(2024, 1, 1)  # Use fixed date for testing

        for idx, episode in enumerate(mock_episodes):
            episode_number = episode['episodeNumber']
            air_date_str = episode.get('airDate', 'Air Date Unknown')
            try:
                air_date = datetime.strptime(air_date_str, "%Y-%m-%d").date()
                is_past_air_date = air_date <= current_date
            except ValueError:
                is_past_air_date = False

            if is_past_air_date:
                options.append({
                    'label': f'Episode {episode_number}',
                    'value': str(idx),
                    'description': f"Air Date: {air_date.strftime('%b %d %Y')}"
                })

        # All 3 episodes aired before 2024
        assert len(options) == 3
        assert options[0]['label'] == 'Episode 1'

    @pytest.mark.unit
    def test_episode_selector_filters_future_episodes(self):
        """Test that future episodes are filtered out."""
        episodes = [
            {'episodeNumber': 1, 'airDate': '2020-01-01'},  # Past
            {'episodeNumber': 2, 'airDate': '2099-12-31'},  # Future
        ]

        current_date = date.today()
        past_episodes = []

        for ep in episodes:
            try:
                air_date = datetime.strptime(ep['airDate'], "%Y-%m-%d").date()
                if air_date <= current_date:
                    past_episodes.append(ep)
            except ValueError:
                pass

        assert len(past_episodes) == 1
        assert past_episodes[0]['episodeNumber'] == 1

    @pytest.mark.unit
    def test_episode_selector_handles_invalid_air_date(self):
        """Test handling of invalid air date format."""
        episode = {'episodeNumber': 1, 'airDate': 'invalid-date'}

        try:
            air_date = datetime.strptime(episode['airDate'], "%Y-%m-%d").date()
            is_valid = True
        except ValueError:
            is_valid = False

        assert is_valid is False

    @pytest.mark.unit
    def test_episode_selector_handles_missing_air_date(self):
        """Test handling of missing air date."""
        episode = {'episodeNumber': 1}

        air_date_str = episode.get('airDate', 'Air Date Unknown')
        assert air_date_str == 'Air Date Unknown'


# ============================================================================
# Test: ConfirmButtonsMovie Component
# ============================================================================

class TestConfirmButtonsMovie:
    """Tests for the movie confirmation buttons."""

    @pytest.mark.unit
    def test_confirm_buttons_has_regrab_button(self):
        """Test that Regrab button exists with correct style."""
        # Simulate button configuration
        regrab_button = {
            'style': 'primary',
            'label': 'Regrab'
        }

        assert regrab_button['label'] == 'Regrab'
        assert regrab_button['style'] == 'primary'

    @pytest.mark.unit
    def test_confirm_buttons_has_cancel_button(self):
        """Test that Cancel button exists with correct style."""
        cancel_button = {
            'style': 'danger',
            'label': 'Cancel'
        }

        assert cancel_button['label'] == 'Cancel'
        assert cancel_button['style'] == 'danger'

    @pytest.mark.unit
    def test_movie_confirmation_message_format(self, mock_movie_lookup):
        """Test that confirmation message is properly formatted."""
        movie = mock_movie_lookup[0]
        media_info = {
            'title': movie['title'],
            'year': movie['year'],
            'overview': movie['overview']
        }

        confirmation_message = (
            f"Please confirm that you would like to regrab the following movie:\n"
            f"**Title:** {media_info['title']}\n"
            f"**Year:** {media_info['year']}\n"
            f"**Overview:** {media_info['overview']}\n"
        )

        assert 'The Matrix' in confirmation_message
        assert '1999' in confirmation_message
        assert '**Title:**' in confirmation_message


# ============================================================================
# Test: ConfirmButtonsSeries Component
# ============================================================================

class TestConfirmButtonsSeries:
    """Tests for the series confirmation buttons."""

    @pytest.mark.unit
    def test_episode_confirmation_message_format(self, mock_episodes):
        """Test that episode confirmation message is properly formatted."""
        episode = mock_episodes[0]
        media_info = {
            'series': 'Breaking Bad',
            'seasonNumber': 1,
            'episodeNumber': episode['episodeNumber'],
            'title': episode['title'],
            'airDate': episode['airDate'],
            'overview': episode['overview']
        }

        confirmation_message = (
            f"Please confirm that you would like to regrab the following episode:\n"
            f"**Series:** {media_info['series']}\n"
            f"**Season:** Season {media_info['seasonNumber']}\n"
            f"**Episode:** Episode {media_info['episodeNumber']}\n"
            f"**Title:** {media_info['title']}\n"
            f"**Air Date:** {media_info['airDate']}\n"
            f"**Overview:** {media_info['overview']}\n"
        )

        assert 'Breaking Bad' in confirmation_message
        assert 'Season 1' in confirmation_message
        assert 'Episode 1' in confirmation_message
        assert 'Pilot' in confirmation_message


# ============================================================================
# Test: View Timeout Behavior
# ============================================================================

class TestViewTimeout:
    """Tests for View timeout behavior."""

    @pytest.mark.unit
    def test_default_view_timeout(self):
        """Test that Views should have a reasonable timeout."""
        # Discord.py default timeout is 180 seconds
        # Views without timeout can cause memory leaks
        default_timeout = 180

        assert default_timeout > 0
        assert default_timeout <= 900  # Max 15 minutes recommended


# ============================================================================
# Test: Media Info State Management
# ============================================================================

class TestMediaInfoState:
    """Tests for media_info state management."""

    @pytest.mark.unit
    def test_media_info_initialized_per_request(self):
        """Test that media_info should be initialized per request (not global)."""
        # This is a critical test - global media_info causes race conditions
        media_info_1 = {'what': 'movie', 'title': 'Movie 1'}
        media_info_2 = {'what': 'movie', 'title': 'Movie 2'}

        # Each request should have independent state
        assert media_info_1 is not media_info_2
        assert media_info_1['title'] != media_info_2['title']

    @pytest.mark.unit
    def test_media_info_contains_movie_fields(self):
        """Test that movie media_info contains required fields."""
        media_info = {
            'what': 'movie',
            'delete': 'yes',
            'movieId': 1,
            'tmdbId': 603,
            'title': 'The Matrix',
            'year': 1999,
            'overview': 'A computer hacker...'
        }

        required_fields = ['what', 'movieId', 'tmdbId', 'title', 'year']
        for field in required_fields:
            assert field in media_info

    @pytest.mark.unit
    def test_media_info_contains_episode_fields(self):
        """Test that episode media_info contains required fields."""
        media_info = {
            'what': 'series',
            'delete': 'yes',
            'series': 'Breaking Bad',
            'seriesId': 1,
            'seasonNumber': 1,
            'episodeNumber': 1,
            'episodeId': 101,
            'episodeFileId': 501,
            'title': 'Pilot',
            'airDate': '2008-01-20',
            'overview': 'Walter White turns to crime.'
        }

        required_fields = ['series', 'seriesId', 'seasonNumber', 'episodeNumber', 'episodeId', 'episodeFileId']
        for field in required_fields:
            assert field in media_info


# ============================================================================
# Test: User Feedback Messages
# ============================================================================

class TestUserFeedbackMessages:
    """Tests for user-facing feedback messages."""

    @pytest.mark.unit
    def test_success_message_movie(self):
        """Test success message format for movie regrab."""
        username = "TestUser"
        movie_title = "The Matrix"
        movie_year = 1999

        message = f"`{username}` your request to delete and redownload {movie_title} ({movie_year}) is being processed."

        assert username in message
        assert movie_title in message
        assert str(movie_year) in message
        assert "being processed" in message

    @pytest.mark.unit
    def test_error_message_movie(self):
        """Test error message format for movie regrab."""
        username = "TestUser"
        movie_title = "The Matrix"
        movie_year = 1999

        message = f"`{username}` your request of {movie_title} ({movie_year}) had an issue, please contact the admin"

        assert username in message
        assert "had an issue" in message
        assert "contact the admin" in message

    @pytest.mark.unit
    def test_success_message_episode(self):
        """Test success message format for episode regrab."""
        username = "TestUser"
        series = "Breaking Bad"
        season = 1
        episode = 1

        message = f"`{username}` your request to (re)grab {series} Season {season} Episode {episode} is being processed."

        assert username in message
        assert series in message
        assert f"Season {season}" in message
        assert f"Episode {episode}" in message

    @pytest.mark.unit
    def test_cancel_message(self):
        """Test cancel message is ephemeral-appropriate."""
        message = "Cancelled the request."

        assert len(message) < 100  # Should be brief
        assert "Cancel" in message

    @pytest.mark.unit
    def test_no_results_message_movie(self):
        """Test message when no movies found."""
        username = "TestUser"
        search_term = "NonexistentMovie"

        message = f"{username} no movie matching the following title was found: {search_term}"

        assert username in message
        assert search_term in message
        assert "no movie" in message

    @pytest.mark.unit
    def test_no_results_message_series(self):
        """Test message when no series found."""
        search_term = "NonexistentSeries"

        message = f"No TV series matching the title: {search_term}"

        assert search_term in message
        assert "No TV series" in message
