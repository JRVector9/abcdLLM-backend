import time

import psutil


_start_time = time.time()


def get_system_metrics() -> dict:
    uptime_secs = time.time() - _start_time
    days = int(uptime_secs // 86400)
    hours = int((uptime_secs % 86400) // 3600)
    uptime_str = f"{days} days, {hours} hours" if days else f"{hours} hours"

    cpu = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent

    return {
        "cpu": cpu,
        "memory": memory,
        "disk": disk,
        "uptime": uptime_str,
    }
