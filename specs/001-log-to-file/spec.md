# Feature Specification: Log to File

## Overview
Convert discord_monitor console output to file-based logging to support packaged application deployments where console output is not visible.

## User Stories

### US-001: Log Messages to File
**As a** user running discord_monitor as a packaged application  
**I want** all monitored Discord messages to be written to a log file  
**So that** I can view the message history even without console access

### US-002: Configurable Log Output
**As a** system administrator  
**I want** to configure log file path and rotation settings via config.yaml  
**So that** I can manage log storage and retention

### US-003: Banner and Status Logging
**As a** user debugging the application  
**I want** startup banners and status messages to also be logged  
**So that** I can verify the application started correctly

## Functional Requirements

### FR-001: Replace Console Prints
- Replace all `print()` statements in discord_monitor.py with appropriate logging calls
- Message content should use `logger.info()`
- Startup banner should use `logger.info()`
- Shutdown message should use `logger.info()`

### FR-002: Existing Config Compatibility
- Maintain compatibility with existing `logging` configuration in config.yaml
- Respect `save_to_file` and `log_file` settings already present
- Default behavior: log to both console and file when `save_to_file: true`

### FR-003: Log Format
- Use consistent log format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- Include timezone-aware timestamps
- Ensure non-ASCII characters (Chinese, emoji) are handled correctly

## Technical Notes

### Current State
- discord_monitor uses `print()` at lines 319-327 (banner), 368 (messages), 495 (shutdown)
- config.yaml already has logging configuration section
- setup_logging() method exists and configures root logger

### Target State
- All output goes through Python logging framework
- Console output can be disabled via config
- File output respects config.yaml settings
- No breaking changes to existing configurations

## Acceptance Criteria

- [ ] All `print()` statements removed from discord_monitor.py
- [ ] Messages appear in log file when `save_to_file: true`
- [ ] Console output still works when running interactively
- [ ] Chinese characters and emoji render correctly in log files
- [ ] Existing config.yaml files work without modification
- [ ] Log file path is configurable via config.yaml

## Related Files
- `discord_monitor/discord_monitor.py`
- `discord_monitor/config.yaml`
