"""
Shared fixtures and configuration for Regrabarr tests.
"""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def sample_config():
    """Returns a sample configuration dictionary for unit tests."""
    return {
        'bot': {
            'token': 'test_token_12345',
            'regrab_movie': 'regrab_movie',
            'regrab_episode': 'regrab_episode'
        },
        'sonarr': {
            'api_key': 'test_sonarr_api_key',
            'url': 'http://localhost:8989/api/v3'
        },
        'radarr': {
            'api_key': 'test_radarr_api_key',
            'url': 'http://localhost:7878/api/v3'
        }
    }


@pytest.fixture
def config_file(tmp_path, sample_config):
    """Creates a temporary config file for testing."""
    config_path = tmp_path / "config.yml"
    with open(config_path, 'w') as f:
        yaml.dump(sample_config, f)
    return config_path


@pytest.fixture
def live_config():
    """
    Loads the live configuration for integration tests.
    Skip if config doesn't exist.
    """
    config_paths = [
        Path(__file__).parent.parent / "config" / "config.yml",
        Path("/config/config.yml"),
    ]

    for config_path in config_paths:
        if config_path.exists():
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)

    pytest.skip("No live config found for integration tests")


# ============================================================================
# Mock Response Fixtures
# ============================================================================

@pytest.fixture
def mock_quality_profiles():
    """Sample quality profiles response from Sonarr/Radarr."""
    return [
        {'id': 1, 'name': 'Any'},
        {'id': 2, 'name': 'SD'},
        {'id': 3, 'name': '1080p Remux'},
        {'id': 4, 'name': '4K'},
    ]


@pytest.fixture
def mock_root_folders():
    """Sample root folders response from Sonarr/Radarr."""
    return [
        {'id': 1, 'path': '/data/media/movies', 'freeSpace': 1000000000},
        {'id': 2, 'path': '/data/media/movies-4k', 'freeSpace': 500000000},
    ]


@pytest.fixture
def mock_movie_lookup():
    """Sample movie lookup response from Radarr."""
    return [
        {
            'id': 1,
            'title': 'The Matrix',
            'year': 1999,
            'tmdbId': 603,
            'overview': 'A computer hacker learns about the true nature of reality.',
            'hasFile': True,
        },
        {
            'id': 2,
            'title': 'The Matrix Reloaded',
            'year': 2003,
            'tmdbId': 604,
            'overview': 'Neo and the rebels fight against the machines.',
            'hasFile': True,
        },
        {
            'id': 3,
            'title': 'The Matrix Revolutions',
            'year': 2003,
            'tmdbId': 605,
            'overview': 'The human city of Zion defends itself.',
            'hasFile': False,
        },
    ]


@pytest.fixture
def mock_series_lookup():
    """Sample series lookup response from Sonarr."""
    return [
        {
            'id': 1,
            'title': 'Breaking Bad',
            'year': 2008,
            'tvdbId': 81189,
            'overview': 'A high school chemistry teacher turns to making meth.',
            'seasons': [
                {'seasonNumber': 0, 'monitored': False},
                {'seasonNumber': 1, 'monitored': True},
                {'seasonNumber': 2, 'monitored': True},
                {'seasonNumber': 3, 'monitored': True},
                {'seasonNumber': 4, 'monitored': True},
                {'seasonNumber': 5, 'monitored': True},
            ]
        },
        {
            'id': 2,
            'title': 'Better Call Saul',
            'year': 2015,
            'tvdbId': 273181,
            'overview': 'The trials of Jimmy McGill becoming Saul Goodman.',
            'seasons': [
                {'seasonNumber': 1, 'monitored': True},
                {'seasonNumber': 2, 'monitored': True},
            ]
        },
    ]


@pytest.fixture
def mock_episodes():
    """Sample episode list response from Sonarr."""
    return [
        {
            'id': 101,
            'seriesId': 1,
            'seasonNumber': 1,
            'episodeNumber': 1,
            'title': 'Pilot',
            'airDate': '2008-01-20',
            'overview': 'Walter White turns to crime.',
            'episodeFileId': 501,
            'hasFile': True,
        },
        {
            'id': 102,
            'seriesId': 1,
            'seasonNumber': 1,
            'episodeNumber': 2,
            'title': "Cat's in the Bag...",
            'airDate': '2008-01-27',
            'overview': 'Walt and Jesse deal with the aftermath.',
            'episodeFileId': 502,
            'hasFile': True,
        },
        {
            'id': 103,
            'seriesId': 1,
            'seasonNumber': 1,
            'episodeNumber': 3,
            'title': '...And the Bag\'s in the River',
            'airDate': '2008-02-10',
            'overview': 'Walt must make a difficult decision.',
            'episodeFileId': 0,
            'hasFile': False,
        },
    ]


# ============================================================================
# Discord Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_discord_interaction():
    """Creates a mock Discord interaction object."""
    interaction = AsyncMock()
    interaction.user = MagicMock()
    interaction.user.name = "TestUser"
    interaction.user.id = 123456789
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.delete_original_response = AsyncMock()
    return interaction


@pytest.fixture
def mock_discord_context():
    """Creates a mock Discord context for slash commands."""
    ctx = AsyncMock()
    ctx.user = MagicMock()
    ctx.user.name = "TestUser"
    ctx.user.id = 123456789
    ctx.response = AsyncMock()
    ctx.channel = MagicMock()
    ctx.channel.id = 987654321
    return ctx


# ============================================================================
# HTTP Session Fixtures
# ============================================================================

@pytest.fixture
def mock_session():
    """Creates a mock requests session."""
    session = MagicMock()
    session.get = MagicMock()
    session.post = MagicMock()
    session.delete = MagicMock()
    return session


@pytest.fixture
def mock_response_factory():
    """Factory to create mock HTTP responses."""
    def _create_response(status_code=200, json_data=None):
        response = MagicMock()
        response.status_code = status_code
        response.json.return_value = json_data or {}
        response.raise_for_status = MagicMock()
        if status_code >= 400:
            from requests.exceptions import HTTPError
            response.raise_for_status.side_effect = HTTPError(f"HTTP {status_code}")
        return response
    return _create_response
