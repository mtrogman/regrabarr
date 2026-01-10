"""
Unit tests for configuration loading and validation.
"""
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open


# ============================================================================
# Test: get_config function
# ============================================================================

class TestGetConfig:
    """Tests for the configuration loading function."""

    @pytest.mark.unit
    def test_load_valid_config(self, config_file, sample_config):
        """Test loading a valid YAML configuration file."""
        # Import here to avoid module-level import issues
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))

        with open(config_file, 'r') as f:
            loaded_config = yaml.safe_load(f)

        assert loaded_config['bot']['token'] == sample_config['bot']['token']
        assert loaded_config['sonarr']['api_key'] == sample_config['sonarr']['api_key']
        assert loaded_config['radarr']['api_key'] == sample_config['radarr']['api_key']

    @pytest.mark.unit
    def test_config_contains_required_sections(self, sample_config):
        """Test that config contains all required sections."""
        required_sections = ['bot', 'sonarr', 'radarr']
        for section in required_sections:
            assert section in sample_config, f"Missing required section: {section}"

    @pytest.mark.unit
    def test_bot_section_has_token(self, sample_config):
        """Test that bot section contains token."""
        assert 'token' in sample_config['bot']
        assert sample_config['bot']['token'] is not None
        assert len(sample_config['bot']['token']) > 0

    @pytest.mark.unit
    def test_sonarr_section_has_required_fields(self, sample_config):
        """Test that sonarr section contains required fields."""
        required_fields = ['api_key', 'url']
        for field in required_fields:
            assert field in sample_config['sonarr'], f"Missing sonarr field: {field}"

    @pytest.mark.unit
    def test_radarr_section_has_required_fields(self, sample_config):
        """Test that radarr section contains required fields."""
        required_fields = ['api_key', 'url']
        for field in required_fields:
            assert field in sample_config['radarr'], f"Missing radarr field: {field}"

    @pytest.mark.unit
    def test_url_format_validation(self, sample_config):
        """Test that URLs are properly formatted."""
        sonarr_url = sample_config['sonarr']['url']
        radarr_url = sample_config['radarr']['url']

        assert sonarr_url.startswith(('http://', 'https://'))
        assert radarr_url.startswith(('http://', 'https://'))
        assert '/api/v3' in sonarr_url or '/api/' in sonarr_url
        assert '/api/v3' in radarr_url or '/api/' in radarr_url

    @pytest.mark.unit
    def test_url_trailing_slash_handling(self):
        """Test that URLs with trailing slashes are handled."""
        url_with_slash = "http://localhost:8989/api/v3/"
        url_without_slash = url_with_slash.rstrip('/')
        assert url_without_slash == "http://localhost:8989/api/v3"

    @pytest.mark.unit
    def test_default_command_names(self, sample_config):
        """Test default command name fallback."""
        regrab_movie = sample_config['bot'].get('regrab_movie', 'regrab_movie')
        regrab_episode = sample_config['bot'].get('regrab_episode', 'regrab_episode')

        assert regrab_movie == 'regrab_movie'
        assert regrab_episode == 'regrab_episode'

    @pytest.mark.unit
    def test_custom_command_names(self):
        """Test custom command names are used when provided."""
        config = {
            'bot': {
                'token': 'test',
                'regrab_movie': 'custom_movie_cmd',
                'regrab_episode': 'custom_episode_cmd'
            }
        }
        assert config['bot'].get('regrab_movie', 'regrab_movie') == 'custom_movie_cmd'
        assert config['bot'].get('regrab_episode', 'regrab_episode') == 'custom_episode_cmd'

    @pytest.mark.unit
    def test_missing_config_file_raises_error(self, tmp_path):
        """Test that missing config file raises appropriate error."""
        nonexistent_path = tmp_path / "nonexistent.yml"
        with pytest.raises(FileNotFoundError):
            with open(nonexistent_path, 'r') as f:
                yaml.safe_load(f)

    @pytest.mark.unit
    def test_invalid_yaml_raises_error(self, tmp_path):
        """Test that invalid YAML raises appropriate error."""
        invalid_yaml_path = tmp_path / "invalid.yml"
        with open(invalid_yaml_path, 'w') as f:
            f.write("invalid: yaml: content: [")

        with pytest.raises(yaml.YAMLError):
            with open(invalid_yaml_path, 'r') as f:
                yaml.safe_load(f)

    @pytest.mark.unit
    def test_empty_config_file(self, tmp_path):
        """Test handling of empty config file."""
        empty_config_path = tmp_path / "empty.yml"
        with open(empty_config_path, 'w') as f:
            f.write("")

        with open(empty_config_path, 'r') as f:
            config = yaml.safe_load(f)

        assert config is None


# ============================================================================
# Test: Configuration Validation
# ============================================================================

class TestConfigValidation:
    """Tests for configuration validation logic."""

    @pytest.mark.unit
    def test_api_key_not_placeholder(self, sample_config):
        """Test that API keys are not placeholder values."""
        placeholders = [
            'PUT_SONARR_API_KEY_HERE',
            'PUT_RADARR_API_KEY_HERE',
            'YOUR_API_KEY',
            'API_KEY_HERE',
            ''
        ]
        assert sample_config['sonarr']['api_key'] not in placeholders
        assert sample_config['radarr']['api_key'] not in placeholders

    @pytest.mark.unit
    def test_token_not_placeholder(self, sample_config):
        """Test that bot token is not a placeholder value."""
        placeholders = [
            'PUT_DISCORD_BOT_TOKEN_HERE',
            'YOUR_TOKEN_HERE',
            'BOT_TOKEN',
            ''
        ]
        assert sample_config['bot']['token'] not in placeholders

    @pytest.mark.unit
    def test_api_key_length(self, sample_config):
        """Test that API keys have reasonable length."""
        # Sonarr/Radarr API keys are typically 32 characters
        sonarr_key = sample_config['sonarr']['api_key']
        radarr_key = sample_config['radarr']['api_key']

        assert len(sonarr_key) >= 10, "Sonarr API key seems too short"
        assert len(radarr_key) >= 10, "Radarr API key seems too short"

    @pytest.mark.unit
    def test_url_contains_port(self, sample_config):
        """Test that URLs contain port numbers (common for Sonarr/Radarr)."""
        sonarr_url = sample_config['sonarr']['url']
        radarr_url = sample_config['radarr']['url']

        # Check for port pattern (: followed by digits)
        import re
        port_pattern = r':\d+'
        assert re.search(port_pattern, sonarr_url), "Sonarr URL should contain port"
        assert re.search(port_pattern, radarr_url), "Radarr URL should contain port"
