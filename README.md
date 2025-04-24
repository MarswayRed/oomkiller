# OOM Killer  
一个简单的 Python 服务，用于监控系统内存使用情况。当可用内存或交换空间低于配置的阈值时，它会尝试终止内存占用最高的进程，以释放资源。
---
**<a href="https://github.com/MarswayRed/oomkiller/blob/main/README_en.md">English Doc</a>**

## 功能

- 定期检查可用物理内存和交换空间百分比。
- 可配置的内存/交换空间阈值、检查间隔和终止超时时间。
- 可配置需要排除的进程名/命令行关键字和用户。
- 优先使用 SIGTERM 尝试优雅终止，超时后使用 SIGKILL 强制终止。
- 作为 systemd 服务运行，日志通过 `journalctl` 查看。

## 依赖

- Python 3.6 +
- `psutil` Python 库

## 本地安装运行、开发
> 本脚本需要 root 用户运行，以确保其对大部分进程有效
1.  **安装依赖:**
    ```bash
    sudo pip install -r requirements.txt
    ```

2. **从本地配置启动**
    ```bash
    sudo python oomkiller.py --config oomkiller.conf
    ```


3.  **以服务运行**  
    1. 新建一个用以调起该程序的守护脚本，其中第一行`#!/usr/bin/env python3`可替换为你所需的 Python3 解释器（如Conda），第二行替换为本地仓库的位置
    ```bash
    sudo vim /usr/bin/oomkiller-daemon
    # oomkiller-daemon
    #!/usr/bin/env python3
    /opt/oomkiller/oomkiller.py
    ```
    2. 授予脚本执行权限
    ```bash
    sudo chmod +x /usr/bin/oomkiller-daemon /opt/oomkiller/oomkiller.py
 
    3. 将 `oomkiller.service` 文件复制到 systemd 的系统服务目录，并启动服务
    ```bash
    sudo cp oomkiller.service /lib/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable oomkiller.service
    ```
    *重要：如果你没有按照 以上步骤进行，请讲 `/lib/systemd/system/oomkiller.service` 文件中的 `ExecStart` 指向你放置 `oomkiller.py` 的正确路径。*

## 使用

- **启动服务:**
  ```bash
  sudo systemctl start oomkiller.service
  ```

- **停止服务:**
  ```bash
  sudo systemctl stop oomkiller.service
  ```

- **查看服务状态:**
  ```bash
  sudo systemctl status oomkiller.service
  ```

- **查看实时日志:**
  ```bash
  sudo journalctl -f -u oomkiller.service
  ```

- **查看所有日志:**
  ```bash
  sudo journalctl -u oomkiller.service
  ```

- **修改配置:**
  编辑 `/etc/default/oomkiller.conf` 文件后，需要重启服务使配置生效：
  ```bash
  sudo systemctl restart oomkiller.service
  ```

## 配置说明
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
## 注意事项
1. 请按需配置 avoid_processes 项，以免 oomkiller 误杀关键进程
2. 该程序的本意为保护公司登录节点的可用性，并非万金油，其优先级在内存耗尽的情况下难以及时运行。它是主动的、预防性的，在系统还未达到内核 OOM Killer 触发的临界点前提前介入，尝试通过杀死高内存消耗的进程来缓解压力。