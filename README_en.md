# OOM Killer

This is a simple Python service designed to monitor system memory usage. When available memory or swap space falls below configured thresholds, it attempts to terminate the process consuming the most memory to free up resources.

## Features

- Periodically checks the percentage of available physical memory and swap space.
- Configurable thresholds for memory/swap, check interval, and termination timeout.
- Configurable list of process names/command line keywords and users to exclude from being killed.
- Prioritizes graceful termination using SIGTERM, followed by forceful termination using SIGKILL after a timeout.
- Runs as a systemd service with logs accessible via `journalctl`.

## Dependencies

- Python 3.6+
- `psutil` Python library

## Local Installation, Running, and Development

> This script requires root privileges to run effectively against most processes.

1.  **Install Dependencies:**
    ```bash
    sudo pip install -r requirements.txt
    ```

2.  **Start with Local Configuration:**
    ```bash
    sudo python oomkiller.py --config oomkiller.conf
    ```

3.  **Run as a Service:**
    1.  Create a daemon script to invoke the program. Replace the first line `#!/usr/bin/env python3` with your desired Python 3 interpreter (like Conda), and the second line with the path to your local repository.
        ```bash
        sudo vim /usr/bin/oomkiller-daemon
        # oomkiller-daemon
        #!/usr/bin/env python3
        /opt/oomkiller/oomkiller.py # Replace with the actual path
        ```
    2.  Grant execution permissions to the scripts.
        ```bash
        sudo chmod +x /usr/bin/oomkiller-daemon /opt/oomkiller/oomkiller.py # Adjust path as needed
        ```
    3.  Copy the `oomkiller.service` file to the systemd system service directory and start the service.
        ```bash
        sudo cp oomkiller.service /lib/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable oomkiller.service
        sudo systemctl start oomkiller.service
        ```
    *Important: If you didn't follow the steps above exactly, make sure the `ExecStart` directive in `/lib/systemd/system/oomkiller.service` points to the correct path where you placed `oomkiller.py` (or the `oomkiller-daemon` script, or preferably the installed `oomkiller` command if using `setup.py`).*

## Usage

- **Start the service:**
  ```bash
  sudo systemctl start oomkiller.service
  ```

- **Stop the service:**
  ```bash
  sudo systemctl stop oomkiller.service
  ```

- **Check service status:**
  ```bash
  sudo systemctl status oomkiller.service
  ```

- **View real-time logs:**
  ```bash
  sudo journalctl -f -u oomkiller.service
  ```

- **View all logs:**
  ```bash
  sudo journalctl -u oomkiller.service
  ```

- **Modify configuration:**
  After editing the `/etc/default/oomkiller.conf` file, you need to restart the service for the changes to take effect:
  ```bash
  sudo systemctl restart oomkiller.service
  ```

## Configurations
```Plain
[General]
# 检测间隔 / Check interval in seconds
query_interval_seconds = 10

# 触发 OOM Killer 的空闲内存阈值 / Threshold of available memory for triggering OOM
# Trigger killing if available memory drops below this percentage
# Example: 10.0 means kill if less than 10% RAM is available (i.e. > 90% used)
min_available_memory_percentage = 5.0

# 触发 OOM Killer 的空闲 Swap 阈值 / Threshold of available swap for triggering OOM
# Trigger killing if available swap drops below this percentage
# Example: 10.0 means kill if less than 10% Swap is available (i.e. > 90% used)
min_available_swap_percentage = 0

# 发送 SIGTERM 后等待进程退出的超时时间 / Timeout for waiting for process to exit after sending SIGTERM
kill_wait_seconds = 5

# 忽略的进程名称 / List of process name to avoid killing
# 区分大小写，使用逗号分割 / Case-sensitive, comma-separated
avoid_processes = systemd, kernel, init, sshd, journald, udevd, rsyslogd, crond, dbus-daemon, NetworkManager, polkitd, login, oomkiller.py, sssd

# 新增：优先杀死的进程名称 / List of process names to prioritize killing
# 如果内存不足，此列表中的进程将优先于其他进程被杀死 / Processes in this list will be killed first when memory is low
# 区分大小写，使用逗号分割 / Case-sensitive, comma-separated
prioritize_kill_processes = 

# 日志文件路径 / Path for the log file
log_path = /var/log/oomkiller.log

# --- 通知设置 / Notification Settings ---
# 是否启用杀死进程后的用户通知 / Enable notification to user after killing process
# 可选值: true / false
enable_notifications = false

# --- 通知渠道配置 / Notification Channel Settings ---
# 仅在 enable_notifications = true 时生效 / Only effective when enable_notifications = true
[Notify]
# 通知渠道类型，例如 feishu, email 等 (当前仅为占位符) / Notification channel type, e.g., feishu, email (currently placeholder)
notification_channel = feishu

# --- 飞书机器人配置 (如果 channel = feishu) / Feishu Bot Config (if channel = feishu) ---
FEISHU_APPID = 
FEISHU_APPSECRET = 
# 机器人 Webhook URL 或 Bot Name (取决于实现方式) / Bot Webhook URL or Bot Name (depends on implementation)
FEISHU_BOTNAME = 
```
---
## Important Notes
1. Please configure the `avoid_processes` item carefully to prevent `oomkiller` from mistakenly killing critical processes.
2. The primary purpose of this program is to protect the availability of the company's login nodes; it is not a universal solution. Its priority might make it difficult to run promptly in severe memory exhaustion scenarios. It is proactive and preventative, intervening before the system reaches the kernel OOM Killer's critical threshold by attempting to alleviate pressure through killing high-memory-consuming processes. 