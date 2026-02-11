"""Unit tests for CLI interface."""

import pytest
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import Mock, patch, MagicMock
from main import app
from core.orchestrator import CriticalError


runner = CliRunner()


@pytest.mark.unit
class TestCLIArgumentParsing:
    """Test CLI argument parsing and validation."""
    
    def test_help_output(self):
        """Test that --help displays usage information."""
        result = runner.invoke(app, ["--help"])
        
        assert result.exit_code == 0
        # Check for key elements in help output
        assert "INPUT_DIR" in result.stdout
        assert "--force" in result.stdout
        assert "--verbose" in result.stdout
        assert "--dry-run" in result.stdout
        assert "theme song" in result.stdout.lower()
    
    def test_missing_required_argument(self):
        """Test that missing input_dir argument shows error."""
        result = runner.invoke(app, [])
        
        assert result.exit_code != 0
        # Typer outputs errors to stderr, but CliRunner captures it
        output = result.stdout + (result.stderr or "")
        assert "Missing argument" in output or "required" in output.lower() or result.exit_code == 2
    
    @patch('main.Orchestrator')
    def test_valid_directory_argument(self, mock_orchestrator, tmp_path):
        """Test that valid directory argument is accepted."""
        # Create a temporary directory
        test_dir = tmp_path / "test_shows"
        test_dir.mkdir()
        
        # Mock the orchestrator
        mock_instance = Mock()
        mock_orchestrator.return_value = mock_instance
        
        result = runner.invoke(app, [str(test_dir)])
        
        assert result.exit_code == 0
        mock_orchestrator.assert_called_once()
        mock_instance.process_directory.assert_called_once()
    
    def test_nonexistent_directory(self):
        """Test that nonexistent directory shows error."""
        result = runner.invoke(app, ["/nonexistent/path/to/shows"])
        
        assert result.exit_code != 0
        # Typer validates path existence and outputs to stderr
        output = result.stdout + (result.stderr or "")
        assert "does not exist" in output.lower() or "invalid" in output.lower() or result.exit_code == 2
    
    def test_file_instead_of_directory(self, tmp_path):
        """Test that providing a file instead of directory shows error."""
        # Create a temporary file
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("test")
        
        result = runner.invoke(app, [str(test_file)])
        
        assert result.exit_code != 0


@pytest.mark.unit
class TestCLIFlags:
    """Test CLI flag handling."""
    
    @patch('main.Orchestrator')
    def test_force_flag_short(self, mock_orchestrator, tmp_path):
        """Test that -f flag is passed to orchestrator."""
        test_dir = tmp_path / "test_shows"
        test_dir.mkdir()
        
        mock_instance = Mock()
        mock_orchestrator.return_value = mock_instance
        
        result = runner.invoke(app, [str(test_dir), "-f"])
        
        assert result.exit_code == 0
        # Check that orchestrator was called with force=True
        call_args = mock_orchestrator.call_args
        assert call_args[0][1] == True  # force parameter
    
    @patch('main.Orchestrator')
    def test_force_flag_long(self, mock_orchestrator, tmp_path):
        """Test that --force flag is passed to orchestrator."""
        test_dir = tmp_path / "test_shows"
        test_dir.mkdir()
        
        mock_instance = Mock()
        mock_orchestrator.return_value = mock_instance
        
        result = runner.invoke(app, [str(test_dir), "--force"])
        
        assert result.exit_code == 0
        call_args = mock_orchestrator.call_args
        assert call_args[0][1] == True  # force parameter
    
    @patch('main.Orchestrator')
    def test_verbose_flag_short(self, mock_orchestrator, tmp_path):
        """Test that -v flag is passed to orchestrator."""
        test_dir = tmp_path / "test_shows"
        test_dir.mkdir()
        
        mock_instance = Mock()
        mock_orchestrator.return_value = mock_instance
        
        result = runner.invoke(app, [str(test_dir), "-v"])
        
        assert result.exit_code == 0
        call_args = mock_orchestrator.call_args
        assert call_args[0][3] == True  # verbose parameter
    
    @patch('main.Orchestrator')
    def test_verbose_flag_long(self, mock_orchestrator, tmp_path):
        """Test that --verbose flag is passed to orchestrator."""
        test_dir = tmp_path / "test_shows"
        test_dir.mkdir()
        
        mock_instance = Mock()
        mock_orchestrator.return_value = mock_instance
        
        result = runner.invoke(app, [str(test_dir), "--verbose"])
        
        assert result.exit_code == 0
        call_args = mock_orchestrator.call_args
        assert call_args[0][3] == True  # verbose parameter
    
    @patch('main.Orchestrator')
    def test_dry_run_flag(self, mock_orchestrator, tmp_path):
        """Test that --dry-run flag is passed to orchestrator."""
        test_dir = tmp_path / "test_shows"
        test_dir.mkdir()
        
        mock_instance = Mock()
        mock_orchestrator.return_value = mock_instance
        
        result = runner.invoke(app, [str(test_dir), "--dry-run"])
        
        assert result.exit_code == 0
        call_args = mock_orchestrator.call_args
        assert call_args[0][2] == True  # dry_run parameter
    
    @patch('main.Orchestrator')
    def test_multiple_flags(self, mock_orchestrator, tmp_path):
        """Test that multiple flags can be combined."""
        test_dir = tmp_path / "test_shows"
        test_dir.mkdir()
        
        mock_instance = Mock()
        mock_orchestrator.return_value = mock_instance
        
        result = runner.invoke(app, [str(test_dir), "-f", "-v", "--dry-run"])
        
        assert result.exit_code == 0
        call_args = mock_orchestrator.call_args
        assert call_args[0][1] == True  # force
        assert call_args[0][2] == True  # dry_run
        assert call_args[0][3] == True  # verbose
    
    @patch('main.Orchestrator')
    def test_default_flag_values(self, mock_orchestrator, tmp_path):
        """Test that flags default to False when not provided."""
        test_dir = tmp_path / "test_shows"
        test_dir.mkdir()
        
        mock_instance = Mock()
        mock_orchestrator.return_value = mock_instance
        
        result = runner.invoke(app, [str(test_dir)])
        
        assert result.exit_code == 0
        call_args = mock_orchestrator.call_args
        assert call_args[0][1] == False  # force
        assert call_args[0][2] == False  # dry_run
        assert call_args[0][3] == False  # verbose


@pytest.mark.unit
class TestCLIErrorHandling:
    """Test CLI error handling and exit codes."""
    
    @patch('main.Orchestrator')
    def test_critical_error_exit_code(self, mock_orchestrator, tmp_path):
        """Test that CriticalError results in exit code 1."""
        test_dir = tmp_path / "test_shows"
        test_dir.mkdir()
        
        mock_instance = Mock()
        mock_instance.process_directory.side_effect = CriticalError("Test critical error")
        mock_orchestrator.return_value = mock_instance
        
        result = runner.invoke(app, [str(test_dir)])
        
        assert result.exit_code == 1
        assert "CRITICAL ERROR" in result.stdout
    
    @patch('main.Orchestrator')
    def test_keyboard_interrupt_exit_code(self, mock_orchestrator, tmp_path):
        """Test that KeyboardInterrupt results in exit code 130."""
        test_dir = tmp_path / "test_shows"
        test_dir.mkdir()
        
        mock_instance = Mock()
        mock_instance.process_directory.side_effect = KeyboardInterrupt()
        mock_orchestrator.return_value = mock_instance
        
        result = runner.invoke(app, [str(test_dir)])
        
        assert result.exit_code == 130
        assert "cancelled" in result.stdout.lower()
    
    @patch('main.Orchestrator')
    def test_unexpected_error_exit_code(self, mock_orchestrator, tmp_path):
        """Test that unexpected exceptions result in exit code 1."""
        test_dir = tmp_path / "test_shows"
        test_dir.mkdir()
        
        mock_instance = Mock()
        mock_instance.process_directory.side_effect = RuntimeError("Unexpected error")
        mock_orchestrator.return_value = mock_instance
        
        result = runner.invoke(app, [str(test_dir)])
        
        assert result.exit_code == 1
        assert "UNEXPECTED ERROR" in result.stdout or "ERROR" in result.stdout
    
    @patch('main.Orchestrator')
    def test_verbose_mode_shows_traceback(self, mock_orchestrator, tmp_path):
        """Test that verbose mode shows traceback on error."""
        test_dir = tmp_path / "test_shows"
        test_dir.mkdir()
        
        mock_instance = Mock()
        mock_instance.process_directory.side_effect = RuntimeError("Test error")
        mock_orchestrator.return_value = mock_instance
        
        result = runner.invoke(app, [str(test_dir), "--verbose"])
        
        assert result.exit_code == 1
        # In verbose mode, should show more error details
        assert "Traceback" in result.stdout or "RuntimeError" in result.stdout


@pytest.mark.unit
class TestCLIOutput:
    """Test CLI output formatting."""
    
    @patch('main.Orchestrator')
    def test_displays_title(self, mock_orchestrator, tmp_path):
        """Test that CLI displays title on startup."""
        test_dir = tmp_path / "test_shows"
        test_dir.mkdir()
        
        mock_instance = Mock()
        mock_orchestrator.return_value = mock_instance
        
        result = runner.invoke(app, [str(test_dir)])
        
        assert result.exit_code == 0
        assert "Show Theme CLI" in result.stdout
    
    @patch('main.Orchestrator')
    def test_orchestrator_invoked(self, mock_orchestrator, tmp_path):
        """Test that orchestrator.process_directory is called."""
        test_dir = tmp_path / "test_shows"
        test_dir.mkdir()
        
        mock_instance = Mock()
        mock_orchestrator.return_value = mock_instance
        
        result = runner.invoke(app, [str(test_dir)])
        
        assert result.exit_code == 0
        mock_instance.process_directory.assert_called_once()
        # Verify the path passed is correct
        call_args = mock_instance.process_directory.call_args
        assert str(call_args[0][0]) == str(test_dir)
