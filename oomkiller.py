#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import sys
import psutil
import signal
import logging
import configparser
import argparse # Import argparse
from logging.handlers import RotatingFileHandler

# --- Constants ---
DEFAULT_CONFIG_PATH = "/etc/oomkiller/oomkiller.conf"
DEFAULT_LOG_PATH = "/var/log/oomkiller.log"
DEFAULT_KILL_WAIT_SECONDS = 5

# --- Globals ---
# 使用 validated_config 存储验证后的配置
validated_config = {}
logger = None

# --- Helper Functions ---
def setup_logging(log_path):
    global logger
    logger = logging.getLogger('oomkiller')
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
                                  datefmt='%Y-%m-%d %H:%M:%S')
    # File handler for rotating logs
    try:
        # 5M per file, keep 3 backups
        file_handler = RotatingFileHandler(log_path, maxBytes=5*1024*1024, backupCount=3)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Failed to setup logging to {log_path}: {e}", file=sys.stderr)
        
    # Stream handler for console and journald
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(lambda record: record.levelno <= logging.WARNING)
    stream_handler.setLevel(logging.INFO)
    logger.addHandler(stream_handler)
    
    stream_err_handler = logging.StreamHandler(sys.stderr)
    stream_err_handler.setFormatter(formatter)
    stream_err_handler.setLevel(logging.ERROR)
    logger.addHandler(stream_err_handler)
    
    logger.info("OOM Killer logging initialized")
    
def load_config(config_path):
    global validated_config
    config = configparser.ConfigParser()

    # --- Read Config File ---
    # 检查配置文件是否存在
    if not os.path.exists(config_path):
        # 使用 print 输出到 stderr，因为 logger 可能尚未完全配置
        print(f"Error: Configuration file not found at {config_path}", file=sys.stderr)
        # 记录错误日志（如果 logger 已基本设置）
        if logger:
            logger.error(f"Configuration file not found at {config_path}")
        sys.exit(1) # 直接退出

    try:
        # 读取配置文件
        read_files = config.read(config_path)
        if not read_files:
             # 如果 read() 成功但返回空列表（例如文件为空或无法解析）
             raise configparser.ParsingError(f"Could not parse config file: {config_path}")
        logger.info(f"Loaded config from {config_path}")

    except configparser.ParsingError as e:
        print(f"Error parsing config file {config_path}: {e}", file=sys.stderr)
        if logger:
             logger.error(f"Error parsing config file {config_path}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading config from {config_path}: {e}", file=sys.stderr)
        if logger:
            logger.error(f"Error loading config from {config_path}: {e}")
        sys.exit(1)

    # --- Validate and Store Config ---
    validated_config = {} # Reset validated config
    try:
        # [General] Validation - 必须存在 General Section
        if not config.has_section('General'):
            raise configparser.NoSectionError('General')

        validated_config['query_interval_seconds'] = config.getint('General', 'query_interval_seconds')
        validated_config['kill_wait_seconds'] = config.getint('General', 'kill_wait_seconds')
        validated_config['min_available_memory_percentage'] = config.getfloat('General', 'min_available_memory_percentage')
        validated_config['min_available_swap_percentage'] = config.getfloat('General', 'min_available_swap_percentage')
        avoid_processes_str = config.get('General', 'avoid_processes')
        validated_config['avoid_processes'] = [p.strip() for p in avoid_processes_str.split(',') if p.strip()]
        prioritize_kill_processes_str = config.get('General', 'prioritize_kill_processes')
        validated_config['prioritize_kill_processes'] = [p.strip() for p in prioritize_kill_processes_str.split(',') if p.strip()]
        validated_config['log_path'] = os.path.abspath(config.get('General', 'log_path'))
        # enable_notifications 仍然是必须的
        validated_config['enable_notifications'] = config.getboolean('General', 'enable_notifications')

        common_processes = set(validated_config['avoid_processes']) & set(validated_config['prioritize_kill_processes'])
        if common_processes:
            logger.warning(f"Processes found in both avoid_processes and prioritize_kill_processes: {','.join(common_processes)}. These processes will be avoided.")
            validated_config['prioritize_kill_processes'] = [p for p in validated_config['prioritize_kill_processes'] if p not in common_processes]

        # [Notify] Validation (only if notifications enabled)
        validated_config['notify'] = {} # Store notify settings in a sub-dict
        if validated_config['enable_notifications']:
            # 如果启用了通知，则 Notify Section 必须存在
            if not config.has_section('Notify'):
                 raise configparser.NoSectionError('Notify (required when enable_notifications is true)')
                 
            validated_config['notify']['notification_channel'] = config.get('Notify', 'notification_channel').strip()
            # 根据 channel 类型决定需要哪些键
            channel = validated_config['notify']['notification_channel'].lower()
            if not channel:
                raise ValueError("notification_channel cannot be empty when notifications are enabled.")

            if channel == 'feishu':
                validated_config['notify']['feishu_appid'] = config.get('Notify', 'feishu_appid').strip()
                validated_config['notify']['feishu_appsecret'] = config.get('Notify', 'feishu_appsecret').strip()
                validated_config['notify']['feishu_botname'] = config.get('Notify', 'feishu_botname', fallback='').strip() # Botname 可选
                if not validated_config['notify']['feishu_appid'] or not validated_config['notify']['feishu_appsecret']:
                     raise ValueError("feishu_appid and feishu_appsecret are required for feishu channel.")
            # Add elif for other channels like 'email' here...
            else:
                logger.warning(f"Unsupported notification channel '{channel}' configured. Validation skipped for channel-specific options.")


    except (ValueError, KeyError, configparser.NoSectionError, configparser.NoOptionError) as e:
        # 提供更清晰的错误来源
        err_msg = f"Invalid or missing required config value in '{config_path}': {e}"
        print(err_msg, file=sys.stderr)
        if logger:
             logger.error(err_msg)
        sys.exit(1)
    except Exception as e:
        err_msg = f"Error validating config from '{config_path}': {e}"
        print(err_msg, file=sys.stderr)
        if logger:
            logger.error(err_msg)
        sys.exit(1)
    
def check_memory_swap_usage():
    """Check memory and swap usage against configured thresholds"""
    try:
        # Get system memory and swap usage
        memory_info = psutil.virtual_memory()
        swap_info = psutil.swap_memory()
        
        # Convert to available percentage
        available_memory_percentage = (memory_info.available / memory_info.total) * 100 if memory_info.total > 0 else 100.0
        available_swap_percentage = (swap_info.free / swap_info.total) * 100 if swap_info.total > 0 else 100.0
        
        memory_ok = available_memory_percentage >= validated_config.get('min_available_memory_percentage')
        swap_ok = available_swap_percentage >= validated_config.get('min_available_swap_percentage')
        
        logger.debug(f"Memory: {memory_info.percent}% used, {available_memory_percentage}% available")
        logger.debug(f"Swap: {swap_info.percent}% used, {available_swap_percentage}% available")
        
        return memory_ok, swap_ok, available_memory_percentage, available_swap_percentage
    except Exception as e:
        logger.error(f"Error checking memory and swap usage: {e}")
        return False, False, 0.0, 0.0
    
def get_memory_hogs(avoid_pids, avoid_names, prioritize_names):
    """Find processes sorted by memory usage, excluding avoid_pids/avoid_names, prioritizing prioritize_names, and include username."""
    try:
        processes = []
        avoid_pids_set = set(avoid_pids)
        avoid_names_set = set(avoid_names)
        prioritize_names_set = set(prioritize_names)
        avoid_pids_set.add(os.getpid())

        # Add 'username' to the attributes list
        for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cmdline', 'status', 'username']):
            try:
                proc_info = proc.info
                if proc_info['pid'] in avoid_pids_set or proc_info['name'] in avoid_names_set:
                    continue
                if not proc_info['cmdline'] or proc_info['status'] in [psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD]:
                    continue

                mem_info = proc_info['memory_info']
                rss = mem_info.rss
                if rss > 0:
                    is_prioritized = proc_info['name'] in prioritize_names_set
                    processes.append({
                        'pid': proc_info['pid'],
                        'name': proc_info['name'],
                        'rss': rss,
                        'cmdline': ' '.join(proc_info['cmdline']) if proc_info['cmdline'] else '',
                        'prioritized': is_prioritized,
                        'username': proc_info['username'] # Store username
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception as e:
                # Log username if available in case of error during iteration
                user = proc_info.get('username', 'N/A') if 'proc_info' in locals() else 'N/A'
                pid = proc_info.get('pid', 'N/A') if 'proc_info' in locals() else 'N/A'
                logger.error(f"Error getting info for process PID={pid}, User={user}: {e}")
                continue

        processes.sort(key=lambda x: (not x['prioritized'], -x['rss']))
        return processes
    except Exception as e:
        logger.error(f"Error getting memory hogs: {e}")
        return []

def kill_process(pid, name, cmdline, rss, username):
    """Attempt to kill a process gracefully (SIGTERM) then forcefully (SIGKILL), and notify user."""
    logger.warning(f"Attempting to kill process PID={pid}, User={username}, Name={name}, RSS={rss // 1024 // 1024}MB")
    logger.debug(f"Full command: {cmdline}") # Log full command on debug level

    hostname = os.uname().nodename # Get hostname for notification message

    try:
        proc = psutil.Process(pid)
        # Verify the username matches before killing, as an extra precaution
        if proc.username() != username:
             logger.error(f"Username mismatch for PID={pid}. Expected '{username}', found '{proc.username()}'. Aborting kill.")
             return False

        proc.terminate()  # Send SIGTERM
        wait_seconds = validated_config.get('kill_wait_seconds', DEFAULT_KILL_WAIT_SECONDS)
        logger.info(f"Sent SIGTERM to PID={pid}, User={username}, Name={name}. Waiting {wait_seconds} seconds...")
        try:
            proc.wait(timeout=wait_seconds)
            logger.info(f"Process terminated gracefully: PID={pid}, User={username}, Name={name}")
            # Send success notification
            message = (f"您在服务器 '{hostname}' 上运行的进程 (PID: {pid}, 名称: {name}) "
                       f"因占用过多内存 (RSS: {rss // 1024 // 1024}MB) 已被 OOM Killer 成功终止。\n"
                       f"命令: {cmdline}")
            send_notification_to_user(username, name, pid, cmdline, message)
            return True
        except psutil.TimeoutExpired:
            logger.warning(f"Process did not terminate after SIGTERM. Sending SIGKILL: PID={pid}, User={username}, Name={name}...")
            proc.kill()  # Send SIGKILL
            try:
                proc.wait(timeout=5) # Give SIGKILL a moment
            except Exception:
                pass # Ignore errors waiting after SIGKILL, just check pid_exists

            if psutil.pid_exists(pid):
                logger.error(f"Failed to kill process PID={pid}, User={username}, Name={name} even with SIGKILL.")
                # Send failure notification
                message = (f"您在服务器 '{hostname}' 上运行的进程 (PID: {pid}, 名称: {name}) "
                           f"因占用过多内存 (RSS: {rss // 1024 // 1024}MB) 触发了 OOM Killer，但未能自动终止。\n"
                           f"请您手动检查并处理该进程。\n"
                           f"命令: {cmdline}")
                send_notification_to_user(username, name, pid, cmdline, message)
                return False
            else:
                logger.info(f"Process killed with SIGKILL: PID={pid}, User={username}, Name={name}")
                 # Send success notification (killed with SIGKILL)
                message = (f"您在服务器 '{hostname}' 上运行的进程 (PID: {pid}, 名称: {name}) "
                           f"因占用过多内存 (RSS: {rss // 1024 // 1024}MB) 且未响应 SIGTERM，已被 OOM Killer 强制终止 (SIGKILL)。\n"
                           f"命令: {cmdline}")
                send_notification_to_user(username, name, pid, cmdline, message)
                return True

    except psutil.NoSuchProcess:
        logger.info(f"Process already exited: PID={pid}, User={username}, Name={name}")
        return True # Already exited, counts as success for our purpose

    except (psutil.AccessDenied, psutil.ZombieProcess) as e:
        logger.error(f"Error killing process PID={pid}, User={username}, Name={name}: {e}. Check permissions.")
        return False

    except Exception as e:
        logger.error(f"Unexpected error killing process PID={pid}, User={username}, Name={name}: {e}")
        return False

def signal_handler(signum, frame):
    """Handle termination signals"""
    logger.info(f"Received signal {signum}, exiting gracefully...")
    sys.exit(0)

# --- Notification Logic ---
def send_notification_to_user(username, process_name, pid, cmdline, message):
    """Sends a notification to the user about a killed or problematic process."""
    if not validated_config.get('enable_notifications', False):
        return # Exit if notifications are disabled globally

    notify_config = validated_config.get('notify', {})
    channel = notify_config.get('notification_channel', '').lower()

    if not channel:
        logger.debug("Notification channel not configured, skipping notification.")
        return # Exit if channel is not set

    logger.info(f"Preparing notification for user '{username}' via channel '{channel}'...")
    logger.debug(f"Notification details: PID={pid}, Name={process_name}, Cmd={cmdline}, Msg={message}")

    # --- Placeholder for actual notification sending logic ---
    if channel == 'feishu':
        # Check Feishu specific config validity again (already checked in load_config but good practice)
        app_id = notify_config.get('feishu_appid')
        app_secret = notify_config.get('feishu_appsecret')
        # bot_name = notify_config.get('feishu_botname') # May need botname or webhook URL
        if not all([app_id, app_secret]):
             logger.error("Feishu notification channel selected, but config (APPID, APPSECRET) is incomplete. Cannot send.")
             return

        logger.info("Attempting to send notification via Feishu (logic not implemented)...")
        # TODO: Implement Feishu notification logic here
        # You might need libraries like requests
        # Example: find user ID based on username, construct message, call Feishu API
        pass # Replace with actual implementation

    # elif channel == 'email':
    #     logger.info("Attempting to send notification via Email (logic not implemented)...")
    #     # TODO: Implement Email notification logic here
    #     pass

    else:
        logger.warning(f"Unsupported notification channel configured: '{channel}'. Cannot send notification.")

    # --- End of Placeholder ---

    logger.debug(f"Notification function for user '{username}' completed.")

# --- Main Execution ---
def main():
    """Main entry point with command-line argument parsing."""
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="OOM Killer with process avoidance, prioritization, and notification.")
    parser.add_argument('--config', default=DEFAULT_CONFIG_PATH,
                        help=f"Path to the configuration file (default: {DEFAULT_CONFIG_PATH})")

    # Subparsers for commands like notify-test
    subparsers = parser.add_subparsers(dest='command', help='Sub-commands')

    # notify-test command
    parser_test = subparsers.add_parser('notify-test', help='Send a test notification to a specified user ID.')
    parser_test.add_argument('user_id', help='The user identifier for the notification channel (e.g., email address, Feishu open_id).')
    parser_test.add_argument('--message', default='This is a test notification from OOM Killer.',
                             help='Optional custom message for the test.')

    args = parser.parse_args()
    config_path = args.config

    # --- Logging Setup (Initial) ---
    # Setup logging early, potentially before reading final log path from config
    # Use a temporary basic setup or the default path initially
    setup_logging(DEFAULT_LOG_PATH)

    # --- Load Configuration ---
    load_config(config_path) # Load config using path from args or default

    # --- Re-setup Logging (Final) ---
    # Use the potentially updated log_path from validated_config
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    # Check if validated_config['log_path'] exists before using it
    final_log_path = validated_config.get('log_path', DEFAULT_LOG_PATH)
    setup_logging(final_log_path)

    # --- Handle notify-test Command ---
    if args.command == 'notify-test':
        logger.info(f"Executing notify-test command for user_id: {args.user_id}")
        if not validated_config.get('enable_notifications'):
            logger.error("Notifications are disabled in the configuration ([General] enable_notifications = false). Cannot send test.")
            sys.exit(1)
        if not validated_config.get('notify', {}).get('notification_channel'):
             logger.error("Notification channel is not configured ([Notify] notification_channel). Cannot send test.")
             sys.exit(1)

        # Use the user_id directly as the 'username' for the test function call
        # The actual implementation inside send_notification_to_user would need to map this ID
        send_notification_to_user(
            username=args.user_id, # Pass the command-line user_id here
            process_name="TestProcess",
            pid=12345,
            cmdline="test command",
            message=args.message
        )
        logger.info("notify-test command finished.")
        sys.exit(0) # Exit after test command

    # --- Normal Operation ---
    logger.info("--- OOM Killer initialized (Normal Operation) ---")
    logger.info(f"Using configuration file: {config_path}")
    logger.info(f"Query interval: {validated_config['query_interval_seconds']} seconds")
    logger.info(f"Kill wait: {validated_config['kill_wait_seconds']} seconds")
    logger.info(f"Min available memory: {validated_config['min_available_memory_percentage']}%")
    logger.info(f"Min available swap: {validated_config['min_available_swap_percentage']}%")
    logger.info(f"Avoid processes: {validated_config['avoid_processes']}")
    logger.info(f"Prioritize kill processes: {validated_config['prioritize_kill_processes']}")
    logger.info(f"Enable notifications: {validated_config['enable_notifications']}") # Log notification status
    if validated_config['enable_notifications']:
         logger.info(f"Notification channel: {validated_config.get('notify', {}).get('notification_channel', 'N/A')}")

    if os.geteuid() != 0:
        logger.warning("OOM Killer not running as root, may lack permissions to query/kill all processes or send notifications depending on implementation.")

    # Register signal handlers only for normal operation
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # --- Main Loop ---
    while True:
        try:
            memory_ok, swap_ok, available_memory_percentage, available_swap_percentage = check_memory_swap_usage()

            if not memory_ok or not swap_ok:
                reason = []
                if not memory_ok: reason.append(f"Memory: {available_memory_percentage:.1f}% available")
                if not swap_ok: reason.append(f"Swap: {available_swap_percentage:.1f}% available")
                logger.warning(f"Memory or swap usage critical: {', '.join(reason)}")

                avoid_pids = set()
                avoid_names = set(validated_config['avoid_processes'])
                prioritize_names = validated_config['prioritize_kill_processes']

                while True:
                    memory_ok, swap_ok, _, _ = check_memory_swap_usage()
                    if memory_ok and swap_ok:
                        logger.info("Memory and swap usage sufficient now.")
                        break

                    hogs = get_memory_hogs(avoid_pids, avoid_names, prioritize_names)
                    #print(hogs) # Removed the debug print added by user

                    if not hogs:
                        logger.error("Low resource condition persists, but no killable memory hogs found.")
                        break

                    target_hog = hogs[0]

                    if target_hog['prioritized']:
                        logger.info(f"Prioritizing kill for process PID={target_hog['pid']}, User={target_hog['username']}, Name={target_hog['name']} based on config.")

                    # Pass username to kill_process
                    killed = kill_process(
                        target_hog['pid'],
                        target_hog['name'],
                        target_hog['cmdline'],
                        target_hog['rss'],
                        target_hog['username'] # Pass username here
                    )

                    if not killed:
                        avoid_pids.add(target_hog['pid'])
                        avoid_names.add(target_hog['name'])
                        logger.error(f"Failed to kill PID={target_hog['pid']}, adding to temporary avoid list.")
                        if len(hogs) <= 1:
                            logger.error("No more processes to try killing in this cycle.")
                            break
                    else:
                        time.sleep(1) # Shorter delay after successful kill

                    time.sleep(1) # Delay to prevent busy-looping

            else:
                logger.info(f"Memory and swap usage normal. Sleeping for {validated_config['query_interval_seconds']} seconds...")
                time.sleep(validated_config['query_interval_seconds'])

        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt, exiting gracefully...")
            break

        except Exception as e:
            logger.exception(f"Unexpected error in main loop: {e}")
            time.sleep(validated_config['query_interval_seconds'])

    logger.info("--- OOM Killer terminated ---")

if __name__ == "__main__":
    main()
                