# BunkerWeb Logger (bw_logger) Integration Guide

This guide provides templates and best practices for integrating the BunkerWeb logging system into Python scripts and modules.

## Quick Start Template

### 1. Basic Import Setup

Add this to the top of every Python file:

```python
from os import sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger
```

### 2. Logger Initialization

Replace old logger setup with one of these options:

#### Option A: Using Custom Title
```python
# Initialize bw_logger module for [description of your module]
logger = setup_logger(
    title="your-module-name",
    log_file_path="/var/log/bunkerweb/your-logfile.log"
)

logger.debug("Debug mode enabled for your-module-name")
```

#### Option B: Using __name__ (Auto-detection)
```python
# Initialize bw_logger module with automatic name detection
logger = setup_logger(
    title=__name__,
    log_file_path="/var/log/bunkerweb/your-logfile.log"
)

logger.debug(f"Debug mode enabled for {__name__}")
```

#### Option C: Let bw_logger Auto-detect (No title parameter)
```python
# Initialize bw_logger module with automatic caller detection
logger = setup_logger(
    log_file_path="/var/log/bunkerweb/your-logfile.log"
)

logger.debug("Debug mode enabled with auto-detected module name")
```

### 3. Common Log File Paths

Use these standard log file paths:

```python
# For Let's Encrypt related modules
log_file_path="/var/log/bunkerweb/letsencrypt.log"

# For scheduler related modules  
log_file_path="/var/log/bunkerweb/scheduler.log"

# For API related modules
log_file_path="/var/log/bunkerweb/api.log"

# For UI related modules
log_file_path="/var/log/bunkerweb/ui.log"

# For generic modules
log_file_path="/var/log/bunkerweb/general.log"
```

## Exception Handling

### ✅ Correct Way - Use `logger.exception()`

The `logger.exception()` method automatically captures the full stack trace and exception details, providing comprehensive debugging information without manual traceback formatting.

```python
try:
    # Your code that might raise an exception
    result = some_operation()
    logger.debug("Operation completed successfully")
    
except FileNotFoundError as e:
    logger.exception("File not found during operation")
    logger.error(f"File error details: {e}")
    
except PermissionError as e:
    logger.exception("Permission denied during operation") 
    logger.error(f"Permission error details: {e}")
    
except Exception as e:
    logger.exception("Unexpected error occurred")
    logger.error(f"Error details: {type(e).__name__}: {e}")
```

**Key Benefits of `logger.exception()`:**
- Automatically includes full stack trace
- Shows exactly where the error occurred
- Includes all nested function calls
- More informative than manual traceback formatting
- Consistent with BunkerWeb logging standards

### ❌ Old Way - Remove These

The old approach using `format_exc()` required manual traceback handling and was less efficient. BunkerWeb's `bw_logger` handles this automatically.

```python
# DELETE these imports:
from traceback import format_exc

# REPLACE this pattern:
try:
    # code
except Exception as e:
    LOGGER.debug(format_exc())  # ❌ Remove this
    LOGGER.error(f"Error: {e}")  # ❌ Replace LOGGER with logger

# WITH this pattern:
try:
    # code  
except Exception as e:
    logger.exception("Clear description of what failed")
    logger.error(f"Error details: {e}")
```

**Why the old way is problematic:**
- Manual traceback formatting is error-prone
- Inconsistent error reporting across modules
- More verbose and harder to maintain
- Missing automatic context that `bw_logger` provides

## Debug Logging Best Practices

### Function Entry/Exit Tracking

```python
def process_certificates(cert_list):
    logger.debug(f"process_certificates() called with {len(cert_list)} certificates")
    
    processed_count = 0
    for cert in cert_list:
        logger.debug(f"Processing certificate {processed_count + 1}/{len(cert_list)}: {cert.name}")
        # Processing logic
        processed_count += 1
    
    logger.debug(f"Certificate processing completed - {processed_count} certificates processed")
    return processed_count
```

### Variable and State Tracking

```python
def configure_system():
    config_file = "/etc/bunkerweb/config.conf"
    logger.debug(f"Loading configuration from: {config_file}")
    
    settings = load_config(config_file)
    logger.debug(f"Loaded {len(settings)} configuration settings")
    
    for key, value in settings.items():
        logger.debug(f"Applying setting {key}: {value}")
        apply_setting(key, value)
    
    logger.debug("System configuration completed successfully")
```

### API/Network Operations

```python
def make_api_request(url, data):
    logger.debug(f"Making API request to: {url}")
    logger.debug(f"Request payload size: {len(data)} bytes")
    
    try:
        response = requests.post(url, json=data, timeout=30)
        logger.debug(f"API response - status: {response.status_code}, "
                    f"response size: {len(response.content)} bytes")
        
        if response.status_code == 200:
            logger.debug("API request completed successfully")
        else:
            logger.warning(f"API request returned non-200 status: {response.status_code}")
            
        return response
        
    except requests.Timeout:
        logger.exception("API request timed out")
        raise
    except requests.RequestException as e:
        logger.exception(f"API request failed to {url}")
        logger.error(f"Request error details: {e}")
        raise
```

### File Operations

```python
def process_file(file_path):
    logger.debug(f"Processing file: {file_path}")
    
    try:
        # Check file existence
        if not Path(file_path).exists():
            logger.error(f"File does not exist: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Read file
        with open(file_path, 'r') as f:
            content = f.read()
        
        logger.debug(f"File read successfully, {len(content)} characters")
        
        # Process content
        result = transform_content(content)
        logger.debug(f"File processing completed, result size: {len(result)}")
        
        return result
        
    except PermissionError:
        logger.exception(f"Permission denied accessing file: {file_path}")
        raise
    except Exception as e:
        logger.exception(f"Error processing file: {file_path}")
        logger.error(f"File processing error details: {e}")
        raise
```

## Complete Example Template

```python
#!/usr/bin/env python3

from os import sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Option 1: Custom title
logger = setup_logger(
    title="example-script",
    log_file_path="/var/log/bunkerweb/example.log"
)

# Option 2: Using __name__
# logger = setup_logger(
#     title=__name__,
#     log_file_path="/var/log/bunkerweb/example.log"
# )

# Option 3: Auto-detection
# logger = setup_logger(
#     log_file_path="/var/log/bunkerweb/example.log"
# )

logger.debug(f"Debug mode enabled for {__name__ if '__name__' in locals() else 'example-script'}")

# Process input data and return formatted results.
# Handles validation, transformation, and error recovery.
def process_data(input_data):
    logger.debug(f"process_data() called with {len(input_data)} items")
    
    try:
        # Validate input
        if not input_data:
            logger.warning("Empty input data provided")
            return []
        
        # Process each item
        results = []
        for i, item in enumerate(input_data):
            logger.debug(f"Processing item {i+1}/{len(input_data)}: {item}")
            
            try:
                result = transform_item(item)
                results.append(result)
                logger.debug(f"Item {i+1} processed successfully")
                
            except ValueError as e:
                logger.exception(f"Invalid data in item {i+1}")
                logger.error(f"Item validation error: {e}")
                continue  # Skip invalid items
        
        logger.debug(f"Data processing completed - {len(results)} items processed successfully")
        return results
        
    except Exception as e:
        logger.exception("Unexpected error during data processing")
        logger.error(f"Processing error details: {type(e).__name__}: {e}")
        raise

# Main application entry point.
# Orchestrates the complete processing workflow.
def main():
    logger.debug("Starting main application workflow")
    
    try:
        # Load input data
        input_file = "/path/to/input.json"
        logger.debug(f"Loading input data from: {input_file}")
        
        with open(input_file, 'r') as f:
            data = json.load(f)
        
        logger.debug(f"Input data loaded successfully, {len(data)} records")
        
        # Process data
        results = process_data(data)
        
        # Save results
        output_file = "/path/to/output.json"
        logger.debug(f"Saving results to: {output_file}")
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Application completed successfully - processed {len(results)} items")
        
    except FileNotFoundError as e:
        logger.exception("Required file not found")
        logger.error(f"File error details: {e}")
        return 1
        
    except Exception as e:
        logger.exception("Application execution failed")
        logger.error(f"Fatal error: {type(e).__name__}: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    logger.debug("Script execution started")
    
    try:
        exit_code = main()
        logger.debug(f"Script execution completed with exit code: {exit_code}")
        sys_exit(exit_code)
        
    except KeyboardInterrupt:
        logger.info("Script execution interrupted by user")
        sys_exit(130)
        
    except Exception as e:
        logger.exception("Fatal error during script execution")
        logger.error(f"Unhandled error: {e}")
        sys_exit(1)
```

## Migration Checklist

When updating existing code:

### ✅ Required Changes

- [ ] Add BunkerWeb dependency path setup
- [ ] Import `bw_logger` instead of old logger
- [ ] Replace old logger initialization with `setup_logger()`
- [ ] Change all `LOGGER` instances to `logger`
- [ ] Remove `from traceback import format_exc`
- [ ] Replace `format_exc()` calls with `logger.exception()`
- [ ] Add comprehensive debug logging

### ✅ Best Practices

- [ ] Use appropriate log file paths for your module
- [ ] Add debug logging for function entry/exit
- [ ] Log variable values and state changes
- [ ] Use specific exception types when possible
- [ ] Include context in exception messages
- [ ] Log success cases, not just errors
- [ ] Use consistent logger naming (`logger`)

### ❌ Don't Do These

- [ ] Don't use `format_exc()` for exception handling
- [ ] Don't keep old logger imports
- [ ] Don't skip debug logging in complex functions
- [ ] Don't log sensitive information (passwords, tokens)

## Common Patterns

### Database Operations

```python
def update_database(query, params):
    logger.debug(f"Executing database query: {query[:100]}...")
    logger.debug(f"Query parameters: {len(params)} items")
    
    try:
        cursor.execute(query, params)
        affected_rows = cursor.rowcount
        logger.debug(f"Database query completed, {affected_rows} rows affected")
        return affected_rows
        
    except sqlite3.Error as e:
        logger.exception("Database operation failed")
        logger.error(f"Database error details: {e}")
        raise
```

### Configuration Loading

```python
def load_configuration(config_path):
    logger.debug(f"Loading configuration from: {config_path}")
    
    try:
        config = {}
        with open(config_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    config[key] = value
                    logger.debug(f"Config line {line_num}: {key} = {value}")
        
        logger.debug(f"Configuration loaded successfully, {len(config)} settings")
        return config
        
    except Exception as e:
        logger.exception(f"Failed to load configuration from {config_path}")
        logger.error(f"Configuration error details: {e}")
        raise
```

### Subprocess Execution

```python
def execute_command(command):
    logger.debug(f"Executing command: {' '.join(command)}")
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        logger.debug(f"Command completed with return code: {result.returncode}")
        
        if result.stdout:
            logger.debug(f"Command stdout: {result.stdout[:200]}...")
        if result.stderr:
            logger.debug(f"Command stderr: {result.stderr[:200]}...")
        
        return result
        
    except subprocess.TimeoutExpired:
        logger.exception(f"Command timed out: {' '.join(command)}")
        raise
    except Exception as e:
        logger.exception(f"Command execution failed: {' '.join(command)}")
        logger.error(f"Command error details: {e}")
        raise
```

This guide provides everything needed to properly integrate BunkerWeb logging into your Python modules while maintaining consistency with the project's standards.