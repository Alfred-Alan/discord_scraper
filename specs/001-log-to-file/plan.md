# Implementation Plan: Log to File

## Architecture Overview
Convert discord_monitor from direct console output to file-based logging using Python's standard logging framework.

## Technology Stack
- Python 3.8+ standard logging module
- Existing config.yaml logging configuration
- No external dependencies required

## Implementation Steps

### Step 1: Update print_banner() Method
**File**: `discord_monitor/discord_monitor.py`  
**Lines**: 319-327

Changes:
- Replace `print()` statements with `logger.info()`
- Keep banner formatting using newlines in single log entry
- Ensure visual separation is preserved in log file

### Step 2: Update Message Output in monitor_channel()
**File**: `discord_monitor/discord_monitor.py`  
**Lines**: 368

Changes:
- Replace `print(formatted)` with `logger.info(formatted)`
- Remove or comment out the print statement
- Ensure formatted message content is preserved

### Step 3: Update Shutdown Message
**File**: `discord_monitor/discord_monitor.py`  
**Lines**: 495

Changes:
- Replace `print("\n\n监控已停止")` with `logger.info()`
- Keep message content but route through logger

### Step 4: Verify Logging Configuration
**File**: `discord_monitor/config.yaml`

Verify existing logging section supports file output:
```yaml
logging:
  level: "INFO"
  save_to_file: true
  log_file: "discord_monitor.log"
```

### Step 5: Setup Dual Handler (Optional Enhancement)
**File**: `discord_monitor/discord_monitor.py`
**Method**: `setup_logging()`

Add dual handler support:
- Console handler for interactive use
- File handler for production/logging
- Both use same formatter

## Testing Approach

1. Run with `save_to_file: false` → verify console output works
2. Run with `save_to_file: true` → verify file output works
3. Verify Chinese characters display correctly in log file
4. Verify emoji display correctly in log file
5. Check log file encoding is UTF-8

## Rollback Plan
- All changes are additive (adding logging, removing prints)
- Config.yaml changes are backward compatible
- Can restore prints if needed (though unlikely)
