# Tasks: Log to File Implementation

## Task 1: Replace Banner Print Statements
**Status**: ✅ COMPLETED  
**Priority**: High  
**File**: `discord_monitor/discord_monitor.py`  
**Lines**: 319-327

### Description
Replace print_banner() method's print() statements with logger.info() calls.

### Implementation
```python
# Before:
def print_banner(self):
    print("\n" + "=" * 60)
    print("       Discord 频道消息实时监控")
    ...

# After:
def print_banner(self):
    banner = "\n" + "=" * 60 + "\n"
    banner += "       Discord 频道消息实时监控\n"
    banner += "=" * 60 + "\n"
    banner += f"监控频道数: {len(self.channels)}\n"
    ...
    banner += "-" * 60 + "\n"
    banner += "开始监控... (按 Ctrl+C 停止)\n"
    logger.info(banner)
```

### Validation
- [x] Banner appears in log file when `save_to_file: true`
- [x] Banner still visible in console when running interactively

---

## Task 2: Replace Message Print Statement
**Status**: ✅ COMPLETED  
**Priority**: High  
**File**: `discord_monitor/discord_monitor.py`  
**Lines**: 368

### Description
Replace the message output print() with logger.info().

### Implementation
```python
# Before:
for msg in messages:
    formatted = self.format_message(msg, name)
    print(formatted)

# After:
for msg in messages:
    formatted = self.format_message(msg, name)
    logger.info(formatted)
```

### Validation
- [x] Messages appear in log file
- [x] Messages still visible in console
- [x] Chinese characters display correctly

---

## Task 3: Replace Shutdown Print Statement
**Status**: ✅ COMPLETED  
**Priority**: Medium  
**File**: `discord_monitor/discord_monitor.py`  
**Lines**: 495

### Description
Replace shutdown message print() with logger.info().

### Implementation
```python
# Before:
except KeyboardInterrupt:
    print("\n\n监控已停止")

# After:
except KeyboardInterrupt:
    logger.info("监控已停止")
```

### Validation
- [x] Shutdown message appears in log file

---

## Task 4: Add Console Handler for Interactive Use
**Status**: ✅ COMPLETED (Already Implemented)  
**Priority**: Medium  
**File**: `discord_monitor/discord_monitor.py`  
**Method**: `setup_logging()`

### Description
Add dual handler support (console + file) so users can see output both in console and log file.

### Implementation
Already implemented - setup_logging() creates both console and file handlers when save_to_file is true.

### Validation
- [x] Output appears in both console and file when `save_to_file: true`
- [x] Output appears only in console when `save_to_file: false`

---

## Task 5: Test and Verify
**Status**: ✅ COMPLETED  
**Priority**: High  

### Test Cases
1. Run with `save_to_file: false` → verify console output only
2. Run with `save_to_file: true` → verify both console and file output
3. Verify log file encoding is UTF-8 (supports Chinese)
4. Verify emoji characters are preserved in logs

### Acceptance Criteria
- [x] All print() statements removed
- [x] No regression in existing functionality
- [x] Log files are UTF-8 encoded
- [x] Backward compatible with existing configs
